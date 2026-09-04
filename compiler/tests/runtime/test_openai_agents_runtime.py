from pathlib import Path

from agents import Agent, Runner, set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp
from agents.testing import ScriptedModel, assistant_message, function_call

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import openai_agents as adapter


set_tracing_disabled(True)
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


def test_builds_native_openai_agents_mcp_and_agent_as_tool() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    models = {name: ScriptedModel() for name in package.agents}

    artifact = adapter.build(package, binding(models), strict=False)

    assert all(isinstance(agent, Agent) for agent in artifact.native_agents.values())
    lead = artifact.native_agents["lead-researcher"]
    assert lead.name == "lead-researcher"
    assert lead.handoff_description == package.entry.description
    assert lead.instructions == package.entry.instructions
    assert isinstance(lead.mcp_servers[0], MCPServerStreamableHttp)
    assert {tool.name for tool in lead.tools} >= {"activate_skill", "explorer", "critic"}
    assert status(artifact, "lead-researcher", "name") == "preserved"
    assert status(artifact, "lead-researcher", "description") == "preserved"
    assert status(artifact, "lead-researcher", "instructions") == "preserved"
    assert status(artifact, "lead-researcher", "skills") == "resolved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "skills.resources") == "unverified"
    assert status(artifact, "lead-researcher", "plugins") == "resolved"
    assert status(artifact, "lead-researcher", "delegates") == "preserved"


def test_native_runner_executes_agent_as_tool_and_returns_control_to_parent() -> None:
    package = load_package(DELEGATION / "lead.agent.md", DELEGATION)
    worker_model = ScriptedModel([[assistant_message("worker result")]])
    coordinator_model = ScriptedModel(
        [
            [function_call("worker", {"input": "Analyze this."}, call_id="call-1")],
            [assistant_message("coordinator used worker result")],
        ]
    )
    artifact = adapter.build(
        package,
        binding({"coordinator": coordinator_model, "worker": worker_model}),
        strict=True,
    )

    result = adapter.run(artifact, "Solve the problem.")

    assert result.output == "coordinator used worker result"
    assert len(worker_model.calls) == 1
    assert worker_model.calls[0].system_instructions == package.agents["worker"].instructions
    assert coordinator_model.calls[-1].system_instructions == package.entry.instructions
    assert [event.kind for event in result.observations] == [
        "delegate-started",
        "delegate-returned",
        "runtime-output",
    ]


def test_strict_openai_agents_accepts_the_full_fixture_with_durability_unverified() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    models = {name: ScriptedModel() for name in package.agents}

    artifact = adapter.build(package, binding(models), strict=True)

    assert not artifact.report.has_blocking_loss
    assert artifact.report.has_unverified
    assert artifact.report.module_outcomes()["skills"]["outcome"] == "accepted"
