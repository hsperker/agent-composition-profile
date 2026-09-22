from pathlib import Path

import pytest

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.products import claude_code
from agent_profile_compiler.runtime.mcp_probe import echo_http_server, parse_echo_result

ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
BINDING = {"capabilities": {"reasoning": True, "tool-use": True}, "entry_mode": "main"}

pytestmark = pytest.mark.skipif(not claude_code.available(), reason="claude CLI is not installed")


def test_claude_code_runs_the_compiled_research_team_with_skill_activation_and_subagent_return() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    result = claude_code.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.entry_instructions_in_system_prompt
    assert {"Skill", "Agent"} <= set(result.tools_offered_to_entry)
    assert result.skill_catalog_advertised_before_activation == ["source-evaluation", "query-planning"]
    assert result.skill_body_absent_before_activation
    assert result.skill_activated == "source-evaluation"
    assert result.skill_body_in_context_after_activation
    assert result.skill_body_persisted_in_later_turns
    assert result.subagent_called == "explorer"
    assert result.subagent_ran_with_own_instructions
    assert "Agent" not in result.subagent_tools_offered  # a leaf agent cannot spawn
    assert result.subagent_result_returned_to_caller


def test_claude_code_activates_plugin_mcp_servers_over_stdio_and_streamable_http() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)

    with echo_http_server((PROBE / "plugins" / "local-echo").resolve()):
        result = claude_code.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.entry_instructions_in_system_prompt
    assert set(result.mcp_tools_offered) == {"mcp__echostdio__echo_stdio", "mcp__echohttp__echo_http"}, result.tools_offered_to_entry
    by_label = {parse_echo_result(item["result"]).get("label"): parse_echo_result(item["result"]) for item in result.mcp_results}
    assert set(by_label) == {"stdio", "http"}, result.mcp_results
    assert by_label["stdio"]["plugin_root_env"] is True and by_label["stdio"]["plugin_data_env"] is True
    # Claude Code has no cwd field for MCP servers: the stdio server runs in the project directory.
    assert by_label["stdio"]["cwd"] == "${PROJECT_DIR}"
    assert by_label["http"]["plugin_root_env"] is False
