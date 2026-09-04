from pathlib import Path

import pytest
from llama_index.core.agent.workflow import AgentWorkflow, FunctionAgent
from llama_index.core.llms import MockFunctionCallingLLM
from llama_index.core.llms import ChatMessage
from llama_index.tools.mcp import BasicMCPClient

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import llamaindex as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"


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
    assert status(artifact, "lead-researcher", "skills") == "approximated"
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


def test_strict_llamaindex_rejects_skill_plugin_and_handoff_semantic_losses() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    with pytest.raises(RuntimeCompatibilityError, match="skills.*plugins.*delegates"):
        adapter.build(package, binding(), strict=True)
