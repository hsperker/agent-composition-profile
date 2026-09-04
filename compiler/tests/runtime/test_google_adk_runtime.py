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


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
DELEGATION = ROOT / "examples" / "runtime-probes" / "delegation"


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
