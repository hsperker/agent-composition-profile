from pathlib import Path

import pytest
from crewai import Agent as CrewAgent
from crewai import Crew
from crewai.llms.base_llm import BaseLLM
from crewai.skills.tool import create_skill_loader_tool

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import crewai as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError

import json
from agent_profile_compiler.runtime.mcp_probe import ECHO_TASK, echo_http_server, parse_echo_result


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
PLUGIN_ROOT = (PROBE / "plugins" / "local-echo").resolve()


class FixedCrewLLM(BaseLLM):
    response: str = "Final Answer: deterministic result"
    seen_messages: list = []

    def call(self, messages, tools=None, callbacks=None, available_functions=None, **kwargs):
        self.seen_messages.append(messages)
        return self.response


def binding() -> dict:
    return {
        "capabilities": {
            "reasoning": True,
            "tool-use": True,
            "vision-input": False,
        },
        "models": {
            name: FixedCrewLLM(model=f"deterministic-{name}")
            for name in ("lead-researcher", "explorer", "critic")
        },
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(
        finding.status
        for finding in artifact.report.findings
        if finding.agent == agent and finding.feature == feature
    )


def test_builds_native_crewai_agents_skills_mcp_and_crew_relationship() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    artifact = adapter.build(package, binding(), strict=False)

    assert all(isinstance(agent, CrewAgent) for agent in artifact.native_agents.values())
    assert isinstance(artifact.metadata["crew"], Crew)
    lead = artifact.native_agents["lead-researcher"]
    assert lead.role == "lead-researcher"
    assert lead.goal == package.entry.description
    assert lead.backstory == package.entry.instructions
    assert [skill.frontmatter.name for skill in lead.skills] == [
        "source-evaluation",
        "query-planning",
    ]
    assert all(skill.instructions is None for skill in lead.skills)
    loader = create_skill_loader_tool(lead.skills, source=lead)
    assert loader is not None
    loaded = loader._run("source-evaluation")
    assert "Prefer primary sources" in loaded
    assert lead.mcps[0].url == "https://research.example.com/mcp"
    assert lead.allow_delegation is True
    assert status(artifact, "lead-researcher", "name") == "approximated"
    assert status(artifact, "lead-researcher", "description") == "approximated"
    assert status(artifact, "lead-researcher", "instructions") == "approximated"
    assert status(artifact, "lead-researcher", "skills") == "preserved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "skills.resources") == "unverified"
    assert status(artifact, "lead-researcher", "plugins") == "resolved"
    assert status(artifact, "lead-researcher", "delegates") == "approximated"


def test_runs_a_real_crewai_leaf_agent_with_its_own_prompt() -> None:
    package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)
    only_critic = binding()
    artifact = adapter.build(package, only_critic, strict=False)

    result = adapter.run(artifact, "Challenge this conclusion.")

    assert "deterministic result" in result.output
    messages = only_critic["models"]["critic"].seen_messages
    assert messages
    system_content = next(
        message["content"] for message in messages[0] if message["role"] == "system"
    )
    assert package.entry.instructions.strip() in system_content
    assert result.observations[-1].kind == "runtime-output"


def test_strict_crewai_rejects_role_prompt_and_team_semantic_changes() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    with pytest.raises(RuntimeCompatibilityError, match="name.*description.*instructions.*delegates"):
        adapter.build(package, binding(), strict=True)


class EchoCallingCrewLLM(BaseLLM):
    """Calls every echo tool offered in the native tool schemas, one per turn, then finishes."""

    called: list = []
    seen_tool_names: list = []

    def supports_function_calling(self) -> bool:
        return True

    def call(self, messages, tools=None, callbacks=None, available_functions=None, **kwargs):
        names = sorted(tool.get("function", tool).get("name") for tool in (tools or []))
        self.seen_tool_names.append(names)
        # CrewAI truncates long sanitized names to a hash, so the echo identity can be
        # absent from what the model sees. The probe agent has only MCP tools, so call each once.
        remaining = [name for name in names if name not in self.called]
        if remaining:
            self.called.append(remaining[0])
            return [
                {
                    "id": f"call-{len(self.called)}",
                    "type": "function",
                    "function": {"name": remaining[0], "arguments": json.dumps({"text": ECHO_TASK})},
                }
            ]
        return "echo done"


def test_activates_agent_plugin_mcp_servers_over_stdio_and_streamable_http() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)
    llm = EchoCallingCrewLLM(model="echo-caller")
    artifact = adapter.build(package, {"capabilities": {}, "models": {"plugin-user": llm}}, strict=False)

    with echo_http_server(PLUGIN_ROOT):
        result = adapter.run(artifact, ECHO_TASK, activate_plugins=True)

    assert result.output == "echo done", (result.output, llm.seen_tool_names)
    discovered = next(o.data["tools"] for o in result.observations if o.kind == "mcp-tools-discovered")
    # CrewAI names MCP tools after the server command or URL, not the configured server name.
    assert any(name.endswith("echo_stdio") for name in discovered), discovered
    assert any(name.endswith("echo_http") for name in discovered), discovered
    assert not any(name.startswith(("echostdio", "echohttp")) for name in discovered), discovered
    results = [parse_echo_result(o.data["result"]) for o in result.observations if o.kind == "mcp-tool-result"]
    by_label = {payload.get("label"): payload for payload in results}
    assert set(by_label) == {"stdio", "http"}, (results, llm.seen_tool_names)
    assert by_label["stdio"]["plugin_root_env"] is True and by_label["stdio"]["plugin_data_env"] is True
    # MCPServerStdio has no cwd field, so the server runs in the inherited working directory.
    assert by_label["stdio"]["cwd"] != str(PLUGIN_ROOT)
    assert by_label["http"]["plugin_root_env"] is False


class SpyCrewLLM(BaseLLM):
    """Records the exact messages CrewAI delivers and answers with a constant."""

    seen: list = []

    def call(self, messages, tools=None, callbacks=None, available_functions=None, **kwargs):
        self.seen.append([dict(m) for m in messages] if isinstance(messages, list) else [{"role": "user", "content": messages}])
        return "final answer"


def test_custom_templates_drop_role_and_goal_but_merge_instructions_into_the_user_turn() -> None:
    """CrewAI's template override was probed as a route to core preservation.

    It removes role and goal from the prompt, but CrewAI then builds one combined
    prompt with no system message, so the instructions arrive fused with the task
    text. Persistent context distinct from task input is therefore not available.
    """
    instructions = "# Instructions\n\nTry to falsify the tentative conclusion."

    default_llm = SpyCrewLLM(model="spy")
    CrewAgent(role="critic", goal="critic", backstory=instructions, llm=default_llm, verbose=False).kickoff("Challenge this.")
    templated_llm = SpyCrewLLM(model="spy")
    CrewAgent(
        role="critic",
        goal="critic",
        backstory=instructions,
        llm=templated_llm,
        verbose=False,
        system_template="{backstory}",
        prompt_template="{input}",
    ).kickoff("Challenge this.")

    default_roles = [m["role"] for m in default_llm.seen[0]]
    assert default_roles == ["system", "user"]
    assert "You are critic." in default_llm.seen[0][0]["content"]
    assert "Your personal goal is: critic" in default_llm.seen[0][0]["content"]

    templated_roles = [m["role"] for m in templated_llm.seen[0]]
    assert templated_roles == ["user"]
    only = templated_llm.seen[0][0]["content"]
    assert instructions in only and "Challenge this." in only
    assert "You are critic" not in only and "personal goal" not in only
