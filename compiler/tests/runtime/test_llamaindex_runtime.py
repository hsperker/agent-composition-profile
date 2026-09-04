from pathlib import Path

import pytest
from llama_index.core.agent.workflow import AgentWorkflow, FunctionAgent
from llama_index.core.llms import MockFunctionCallingLLM
from llama_index.core.llms import ChatMessage
from llama_index.tools.mcp import BasicMCPClient

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import llamaindex as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError

from llama_index.core.base.llms.types import ToolCallBlock
from agent_profile_compiler.runtime.mcp_probe import ECHO_TASK, echo_http_server, parse_echo_result

ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
PLUGIN_ROOT = (PROBE / "plugins" / "local-echo").resolve()


def fixed_model(output: str, calls: list) -> MockFunctionCallingLLM:
    def respond(messages, **kwargs):
        calls.append(list(messages))
        return ChatMessage(role="assistant", content=output)

    return MockFunctionCallingLLM(response_generator=respond, is_chat_model=True)


def binding(calls: dict[str, list] | None = None) -> dict:
    calls = calls if calls is not None else {name: [] for name in ("lead-researcher", "explorer", "critic")}
    return {
        "capabilities": {"reasoning": True, "tool-use": True, "vision-input": False},
        "models": {
            name: fixed_model(f"{name} result", calls[name])
            for name in ("lead-researcher", "explorer", "critic")
        },
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(f.status for f in artifact.report.findings if f.agent == agent and f.feature == feature)


def test_builds_native_llamaindex_agents_and_handoff_workflow() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    artifact = adapter.build(package, binding(), strict=False)

    assert all(isinstance(agent, FunctionAgent) for agent in artifact.native_agents.values())
    assert isinstance(artifact.metadata["workflow"], AgentWorkflow)
    lead = artifact.native_agents["lead-researcher"]
    assert lead.name == "lead-researcher"
    assert lead.description == package.entry.description
    assert lead.system_prompt == package.entry.instructions
    assert lead.can_handoff_to == ["explorer", "critic"]
    assert isinstance(artifact.metadata["mcp_clients"]["lead-researcher"][0], BasicMCPClient)
    assert status(artifact, "lead-researcher", "name") == "preserved"
    assert status(artifact, "lead-researcher", "description") == "preserved"
    assert status(artifact, "lead-researcher", "instructions") == "preserved"
    assert status(artifact, "lead-researcher", "skills") == "resolved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "skills.resources") == "unverified"
    assert status(artifact, "lead-researcher", "plugins") == "unsupported"
    assert status(artifact, "lead-researcher", "delegates") == "approximated"


def test_runs_real_llamaindex_leaf_and_passes_persistent_system_prompt() -> None:
    package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)
    calls = {"lead-researcher": [], "explorer": [], "critic": []}
    artifact = adapter.build(package, binding(calls), strict=True)

    result = adapter.run(artifact, "Challenge this.")

    assert result.output == "critic result"
    assert calls["critic"]
    assert any(
        message.role.value == "system" and package.entry.instructions in (message.content or "")
        for message in calls["critic"][0]
    )


def test_strict_llamaindex_rejects_plugin_and_handoff_semantic_losses() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    with pytest.raises(RuntimeCompatibilityError, match="plugins.*delegates"):
        adapter.build(package, binding(), strict=True)


def echo_calling_model() -> MockFunctionCallingLLM:
    """Calls every offered echo tool once, one per turn, then finishes."""

    called: list[str] = []

    def respond(messages, **kwargs):
        offered = sorted(tool.metadata.name for tool in (kwargs.get("tools") or []) if "echo" in tool.metadata.name)
        remaining = [name for name in offered if name not in called]
        if remaining:
            called.append(remaining[0])
            return ChatMessage(
                role="assistant",
                blocks=[ToolCallBlock(tool_call_id=f"call-{len(called)}", tool_name=remaining[0], tool_kwargs={"text": ECHO_TASK})],
            )
        return ChatMessage(role="assistant", content="echo done")

    return MockFunctionCallingLLM(response_generator=respond, is_chat_model=True)

def test_activates_agent_plugin_mcp_servers_over_stdio_and_streamable_http() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)
    binding = {"capabilities": {}, "models": {"plugin-user": echo_calling_model()}, "activate_plugins": True}

    with echo_http_server(PLUGIN_ROOT):
        # The fixture declares cwd, which BasicMCPClient cannot express, so strict mode rejects it.
        with pytest.raises(RuntimeCompatibilityError, match="cwd"):
            adapter.build(package, binding, strict=True)
        artifact = adapter.build(package, binding, strict=False)
        assert status(artifact, "plugin-user", "plugins") == "unsupported"
        result = adapter.run(artifact, ECHO_TASK, activate_plugins=True)

    assert result.output == "echo done"
    # BasicMCPClient has no cwd parameter, so the stdio server runs in the inherited directory.
    assert parse_echo_result(next(o.data["result"] for o in result.observations if o.kind == "mcp-tool-result" and o.data["server"] == "echostdio"))["cwd"] != str(PLUGIN_ROOT)
    discovered = {o.data["server"]: o.data["tools"] for o in result.observations if o.kind == "mcp-tools-discovered"}
    assert set(discovered) == {"echostdio", "echohttp"}, result.observations
    assert all(any("echo" in name for name in names) for names in discovered.values())
    results = {o.data["server"]: parse_echo_result(o.data["result"]) for o in result.observations if o.kind == "mcp-tool-result"}
    assert set(results) == {"echostdio", "echohttp"}, result.observations
    stdio, http = results["echostdio"], results["echohttp"]
    assert stdio["label"] == "stdio" and stdio["plugin_root_env"] is True and stdio["plugin_data_env"] is True
    assert http["label"] == "http" and http["plugin_root_env"] is False
    assert [o.kind for o in result.observations if o.kind == "mcp-activation-failed"] == []
