from pathlib import Path

import pytest

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.products import codex
from agent_profile_compiler.runtime.mcp_probe import echo_http_server, parse_echo_result

ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
BINDING = {"capabilities": {"reasoning": True, "tool-use": True}, "entry_mode": "main",
           "model": "probe-model", "model_reasoning_effort": "low"}

pytestmark = pytest.mark.skipif(not codex.available(), reason="codex CLI is not installed")


@pytest.fixture(autouse=True)
def _needs_mcp_for_the_echo_server():
    pytest.importorskip("mcp")


def test_codex_runs_the_compiled_research_team_with_skill_activation_and_subagent_return() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    result = codex.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.entry_instructions_in_instructions
    assert result.entry_instructions_delivered_as == "user message (AGENTS.md)"
    assert "exec_command" in result.tools_offered_to_entry
    assert set(result.subagent_tools_offered) >= {"spawn_agent", "wait_agent"}
    assert result.skill_catalog_advertised_before_activation == ["source-evaluation", "query-planning"]
    assert result.skill_body_absent_before_activation
    assert result.skill_activated == "source-evaluation"  # activation is a file read of SKILL.md
    assert result.skill_body_in_context_after_activation
    assert result.skill_body_persisted_in_later_turns
    assert result.subagents_advertised == ["explorer", "critic"]  # the project-wide custom agent catalog
    assert result.subagent_called == "explorer"
    assert result.subagent_ran_with_own_instructions
    assert result.subagent_result_returned_to_caller


def test_codex_plugin_mcp_servers_reach_the_main_thread_through_project_config() -> None:
    """Both plugin servers are offered as mcp__<server> namespace tools; the stdio server honors
    cwd and env. Servers start in the background, so a slow one can miss the first step."""
    package = load_package(PROBE / "agent.agent.md", PROBE)

    with echo_http_server((PROBE / "plugins" / "local-echo").resolve()):
        result = codex.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.mcp_tools_offered == ["mcp__echohttp.echo_http", "mcp__echostdio.echo_stdio"], result.mcp_log
    by_label = {parse_echo_result(item["result"]).get("label"): parse_echo_result(item["result"]) for item in result.mcp_results}
    assert set(by_label) == {"stdio", "http"}, result.mcp_results
    assert by_label["stdio"]["cwd"].endswith("plugins/local-echo")
    assert by_label["stdio"]["plugin_root_env"] is True and by_label["stdio"]["plugin_data_env"] is True
