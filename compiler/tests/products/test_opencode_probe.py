from pathlib import Path

import pytest

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.products import opencode
from agent_profile_compiler.runtime.mcp_probe import echo_http_server, parse_echo_result

ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
BINDING = {"capabilities": {"reasoning": True, "tool-use": True}, "entry_mode": "primary"}

pytestmark = pytest.mark.skipif(not opencode.available(), reason="opencode CLI is not installed")


@pytest.fixture(autouse=True)
def _needs_mcp_for_the_echo_server():
    pytest.importorskip("mcp")


def test_opencode_runs_the_compiled_research_team_with_skill_activation_and_subagent_return() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    result = opencode.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.entry_instructions_in_system_prompt
    assert {"skill", "subagent"} <= set(result.tools_offered_to_entry)
    assert result.skill_catalog_advertised_before_activation == ["source-evaluation", "query-planning"]
    assert result.skill_body_absent_before_activation
    assert result.skill_activated == "source-evaluation"
    assert result.skill_body_in_context_after_activation
    assert result.skill_body_persisted_in_later_turns
    assert result.subagents_advertised == ["explorer", "critic"]  # the permission.task allowlist, not the whole project
    assert result.subagent_called == "explorer"
    assert result.subagent_ran_with_own_instructions
    assert result.subagent_result_returned_to_caller


def test_opencode_connects_plugin_mcp_servers_but_offers_no_mcp_tool_to_the_model() -> None:
    """Recorded finding for OpenCode 2.0.14: both plugin servers connect, yet the model is offered
    no MCP tool, neither as a function tool nor through the Code Mode catalog."""
    package = load_package(PROBE / "agent.agent.md", PROBE)

    with echo_http_server((PROBE / "plugins" / "local-echo").resolve()):
        result = opencode.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.entry_instructions_in_system_prompt
    assert result.mcp_servers_connected == {"echostdio": "connected", "echohttp": "connected"}, result.notes
    assert result.mcp_tools_offered == [], result.tools_offered_to_entry
    assert result.mcp_results == []
    assert result.code_mode_search_result is not None and '"items":[]' in result.code_mode_search_result
