from pathlib import Path

from agents import Agent, Runner, set_tracing_disabled
from agents.mcp import MCPServerStreamableHttp
from agents.items import ModelResponse
from agents.models.interface import Model
from agents.testing import ScriptedModel, assistant_message, function_call
from agents.usage import Usage

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import openai_agents as adapter
from agent_profile_compiler.runtime.mcp_probe import ECHO_TASK, echo_http_server, parse_echo_result


set_tracing_disabled(True)
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


class EchoCallingModel(Model):
    """Calls every discovered echo tool once, one per turn, then finishes."""

    def __init__(self) -> None:
        self.called: list[str] = []

    async def get_response(self, system_instructions, input, model_settings, tools, output_schema, handoffs, tracing, *, previous_response_id, conversation_id, prompt):
        remaining = sorted(tool.name for tool in tools if "echo" in tool.name and tool.name not in self.called)
        if remaining:
            self.called.append(remaining[0])
            item = function_call(remaining[0], {"text": ECHO_TASK}, call_id=f"call-{len(self.called)}")
            return ModelResponse(output=[item], usage=Usage(), response_id=None)
        return ModelResponse(output=[assistant_message("echo done")], usage=Usage(), response_id=None)

    def stream_response(self, *args, **kwargs):
        raise NotImplementedError

def test_activates_agent_plugin_mcp_servers_over_stdio_and_streamable_http() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)
    artifact = adapter.build(package, binding({"plugin-user": EchoCallingModel()}), strict=True)

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
