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
    assert "skill" in result.tools_offered_to_entry
    assert {"subagent", "task"} & set(result.tools_offered_to_entry)
    assert result.skill_catalog_advertised_before_activation == ["source-evaluation", "query-planning"]
    assert result.skill_body_absent_before_activation
    assert result.skill_activated == "source-evaluation"
    assert result.skill_body_in_context_after_activation
    assert result.skill_body_persisted_in_later_turns
    assert result.subagents_advertised == ["explorer", "critic"]  # the permission.task allowlist, not the whole project
    assert result.subagent_called == "explorer"
    assert result.subagent_ran_with_own_instructions
    assert result.subagent_result_returned_to_caller


def test_opencode_plugin_mcp_servers_connect_and_tool_exposure_depends_on_the_major_version() -> None:
    """v1 exposes plugin MCP servers as <server>_<tool> function tools and honors cwd.
    v2.0.14 connects both servers but offers the model no MCP tool, directly or through Code Mode."""
    package = load_package(PROBE / "agent.agent.md", PROBE)

    with echo_http_server((PROBE / "plugins" / "local-echo").resolve()):
        result = opencode.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.entry_instructions_in_system_prompt
    assert result.mcp_servers_connected == {"echostdio": "connected", "echohttp": "connected"}, result.notes
    if opencode.major_version() >= 2:
        assert result.mcp_tools_offered == [], result.tools_offered_to_entry
        assert result.mcp_results == []
        assert result.code_mode_search_result is not None and '"items":[]' in result.code_mode_search_result
    else:
        assert result.mcp_tools_offered == ["echohttp_echo_http", "echostdio_echo_stdio"], result.tools_offered_to_entry
        by_label = {parse_echo_result(item["result"]).get("label"): parse_echo_result(item["result"]) for item in result.mcp_results}
        assert set(by_label) == {"stdio", "http"}, result.mcp_results
        assert by_label["stdio"]["plugin_root_env"] is True and by_label["stdio"]["plugin_data_env"] is True
        assert by_label["stdio"]["cwd"] == str((PROBE / "plugins" / "local-echo").resolve())
        assert by_label["http"]["plugin_root_env"] is False
