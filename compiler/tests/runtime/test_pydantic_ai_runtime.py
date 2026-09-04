from pathlib import Path

import pytest
from fastmcp.client.transports import StreamableHttpTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.test import TestModel

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import pydantic_ai as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
DELEGATION = ROOT / "examples" / "runtime-probes" / "delegation"


def binding(models: dict) -> dict:
    return {
        "capabilities": {"reasoning": True, "tool-use": True, "vision-input": False},
        "models": models,
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(f.status for f in artifact.report.findings if f.agent == agent and f.feature == feature)


def test_builds_native_pydantic_agents_mcp_and_delegate_tools() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    models = {
        name: TestModel(custom_output_text=f"unused-{name}") for name in package.agents
    }

    artifact = adapter.build(package, binding(models), strict=False)

    assert all(isinstance(agent, Agent) for agent in artifact.native_agents.values())
    lead = artifact.native_agents["lead-researcher"]
    assert lead.name == "lead-researcher"
    assert lead.description == package.entry.description
    assert {tool.id for tool in lead.toolsets if isinstance(tool, MCPToolset)} == {
        "research"
    }
    mcp = next(tool for tool in lead.toolsets if isinstance(tool, MCPToolset))
    assert isinstance(mcp.client.transport, StreamableHttpTransport)
    assert set(lead._function_toolset.tools) >= {"activate_skill", "explorer", "critic"}
    assert status(artifact, "lead-researcher", "name") == "preserved"
    assert status(artifact, "lead-researcher", "description") == "preserved"
    assert status(artifact, "lead-researcher", "instructions") == "preserved"
    assert status(artifact, "lead-researcher", "skills") == "approximated"
    assert status(artifact, "lead-researcher", "plugins") == "resolved"
    assert status(artifact, "lead-researcher", "delegates") == "resolved"


def test_pydantic_runner_executes_adapter_delegate_tool_and_returns_to_parent() -> None:
    package = load_package(DELEGATION / "lead.agent.md", DELEGATION)
    artifact = adapter.build(
        package,
        binding(
            {
                "coordinator": TestModel(
                    call_tools=["worker"], custom_output_text="coordinator used worker result"
                ),
                "worker": TestModel(custom_output_text="worker result"),
            }
        ),
        strict=True,
    )

    result = adapter.run(artifact, "Solve the problem.")

    assert result.output == "coordinator used worker result"
    assert [event.kind for event in result.observations] == [
        "delegate-started",
        "delegate-returned",
        "runtime-output",
    ]
    assert result.observations[1].data["result"] == "worker result"


def test_strict_pydantic_ai_rejects_skill_authority_approximation() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    models = {
        name: TestModel(custom_output_text=f"unused-{name}") for name in package.agents
    }

    with pytest.raises(RuntimeCompatibilityError, match="skills"):
        adapter.build(package, binding(models), strict=True)
