from pathlib import Path

import pytest
from google.adk.agents import LlmAgent
from google.adk.models import BaseLlm, LlmResponse
from google.adk.tools import AgentTool
from google.adk.tools.mcp_tool import McpToolset
from google.genai import types

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import google_adk as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError
from pydantic import Field

from agent_profile_compiler.runtime.mcp_probe import ECHO_TASK, echo_http_server, parse_echo_result


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
DELEGATION = ROOT / "examples" / "runtime-probes" / "delegation"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
PLUGIN_ROOT = (PROBE / "plugins" / "local-echo").resolve()


class ScriptedLlm(BaseLlm):
    responses: list[LlmResponse]
    seen_requests: list = []

    async def generate_content_async(self, llm_request, stream=False):
        self.seen_requests.append(llm_request)
        yield self.responses.pop(0)


def text_response(text: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(role="model", parts=[types.Part.from_text(text=text)])
    )


def function_response(name: str, request: str) -> LlmResponse:
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part.from_function_call(
                    name=name,
                    args={"request": request},
                )
            ],
        )
    )


def binding(models: dict) -> dict:
    return {
        "capabilities": {"reasoning": True, "tool-use": True, "vision-input": False},
        "models": models,
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(f.status for f in artifact.report.findings if f.agent == agent and f.feature == feature)


def test_builds_native_adk_agents_mcp_and_agent_tools() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    models = {
        name: ScriptedLlm(model=f"scripted-{name}", responses=[text_response("unused")])
        for name in package.agents
    }

    artifact = adapter.build(package, binding(models), strict=False)

    assert all(isinstance(agent, LlmAgent) for agent in artifact.native_agents.values())
    lead = artifact.native_agents["lead-researcher"]
    assert lead.name == "lead_researcher"
    assert artifact.metadata["source_to_native"]["lead-researcher"] == "lead_researcher"
    assert lead.description == package.entry.description
    assert callable(lead.instruction)
    assert any(isinstance(tool, McpToolset) for tool in lead.tools)
    assert {tool.name for tool in lead.tools if isinstance(tool, AgentTool)} == {
        "explorer",
        "critic",
    }
    assert status(artifact, "lead-researcher", "name") == "resolved"
    assert status(artifact, "lead-researcher", "description") == "preserved"
    assert status(artifact, "lead-researcher", "instructions") == "preserved"
    assert status(artifact, "lead-researcher", "skills") == "resolved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "skills.resources") == "unverified"
    assert status(artifact, "lead-researcher", "plugins") == "resolved"
    assert status(artifact, "lead-researcher", "delegates") == "approximated"


def test_adk_runner_executes_nested_agent_tool_and_returns_to_parent() -> None:
    package = load_package(DELEGATION / "lead.agent.md", DELEGATION)
    worker_model = ScriptedLlm(
        model="scripted-worker", responses=[text_response("worker result")]
    )
    coordinator_model = ScriptedLlm(
        model="scripted-coordinator",
        responses=[
            function_response("worker", "Analyze this."),
            text_response("coordinator used worker result"),
        ],
    )
    artifact = adapter.build(
        package,
        binding({"coordinator": coordinator_model, "worker": worker_model}),
        strict=False,
    )

    result = adapter.run(artifact, "Solve the problem.")

    assert result.output == "coordinator used worker result"
    assert len(worker_model.seen_requests) == 1
    assert len(coordinator_model.seen_requests) == 2
    assert [event.kind for event in result.observations] == [
        "delegate-started",
        "delegate-returned",
        "runtime-output",
    ]


def test_strict_adk_rejects_shared_state_delegate_approximation() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    models = {
        name: ScriptedLlm(model=f"scripted-{name}", responses=[text_response("unused")])
        for name in package.agents
    }

    with pytest.raises(RuntimeCompatibilityError, match="delegates"):
        adapter.build(package, binding(models), strict=True)


class EchoCallingLlm(BaseLlm):
    """Calls every echo tool offered in the request, one per turn, then finishes."""

    called: list[str] = Field(default_factory=list)

    async def generate_content_async(self, llm_request, stream=False):
        remaining = sorted(name for name in llm_request.tools_dict if "echo" in name and name not in self.called)
        if remaining:
            self.called.append(remaining[0])
            yield LlmResponse(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_function_call(name=remaining[0], args={"text": ECHO_TASK})],
                )
            )
        else:
            yield text_response("echo done")

def test_activates_agent_plugin_mcp_servers_over_stdio_and_streamable_http() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)
    artifact = adapter.build(package, binding({"plugin-user": EchoCallingLlm(model="echo-caller")}), strict=True)

    with echo_http_server(PLUGIN_ROOT):
        result = adapter.run(artifact, ECHO_TASK, activate_plugins=True)

    assert result.output == "echo done"
    discovered = {o.data["server"]: o.data["tools"] for o in result.observations if o.kind == "mcp-tools-discovered"}
    assert set(discovered) == {"echostdio", "echohttp"}, result.observations
    assert all(any("echo" in name for name in names) for names in discovered.values())
    results = {o.data["server"]: parse_echo_result(o.data["result"]) for o in result.observations if o.kind == "mcp-tool-result"}
    assert set(results) == {"echostdio", "echohttp"}, result.observations
    stdio, http = results["echostdio"], results["echohttp"]
    assert stdio["label"] == "stdio" and stdio["plugin_root_env"] is True and stdio["plugin_data_env"] is True
    assert stdio["cwd"] == str(PLUGIN_ROOT)
    assert http["label"] == "http" and http["plugin_root_env"] is False
    assert [o.kind for o in result.observations if o.kind == "mcp-activation-failed"] == []
