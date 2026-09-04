from pathlib import Path

from fastmcp.client.transports import StreamableHttpTransport
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.test import TestModel

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import pydantic_ai as adapter

from agent_profile_compiler.runtime.mcp_probe import ECHO_TASK, echo_http_server, parse_echo_result


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
DELEGATION = ROOT / "examples" / "runtime-probes" / "delegation"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
PLUGIN_ROOT = (PROBE / "plugins" / "local-echo").resolve()


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
    assert status(artifact, "lead-researcher", "skills") == "resolved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "skills.resources") == "unverified"
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


def test_strict_pydantic_ai_accepts_the_full_fixture_with_durability_unverified() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    models = {
        name: TestModel(custom_output_text=f"unused-{name}") for name in package.agents
    }

    artifact = adapter.build(package, binding(models), strict=True)

    assert not artifact.report.has_blocking_loss
    assert artifact.report.has_unverified


# TestModel(call_tools="all") calls every discovered tool with schema-derived arguments.

def test_activates_agent_plugin_mcp_servers_over_stdio_and_streamable_http() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)
    artifact = adapter.build(
        package, binding({"plugin-user": TestModel(call_tools="all", custom_output_text="echo done")}), strict=True
    )

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
