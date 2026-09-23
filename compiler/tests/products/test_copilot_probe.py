from pathlib import Path

import pytest

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.products import copilot
from agent_profile_compiler.runtime.mcp_probe import echo_http_server, parse_echo_result

ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"
BINDING = {"capabilities": {"reasoning": True, "tool-use": True}}

pytestmark = pytest.mark.skipif(not copilot.available(), reason="copilot CLI is not installed")


@pytest.fixture(autouse=True)
def _needs_mcp_for_the_echo_server():
    pytest.importorskip("mcp")


def test_copilot_runs_the_compiled_research_team_with_skill_activation_and_subagent_return() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    result = copilot.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.entry_instructions_in_system_prompt
    assert {"skill", "task"} <= set(result.tools_offered_to_entry)
    assert result.skill_catalog_advertised_before_activation == ["source-evaluation", "query-planning"]
    assert result.skill_body_absent_before_activation
    assert result.skill_activated == "source-evaluation"
    assert result.skill_body_in_context_after_activation
    assert result.skill_body_persisted_in_later_turns
    # The task tool lists every custom agent in the project, the entry itself included:
    # the `agents` allowlist is not what the CLI advertises, and it does not refuse an unlisted agent.
    assert result.subagents_advertised == ["lead-researcher", "explorer", "critic"]
    assert result.subagent_called == "explorer"
    assert result.subagent_ran_with_own_instructions
    assert result.subagent_result_returned_to_caller
    assert result.unlisted_subagent_call is not None and result.unlisted_subagent_call.startswith("ran")


def test_copilot_plugin_mcp_servers_from_the_agent_file_reach_the_model_without_stdio_cwd() -> None:
    """The CLI reads the agent file's mcp-servers block. Both servers connect and their tools are
    offered as <server>-<tool>; the stdio server gets env but runs in the project, not the plugin root."""
    package = load_package(PROBE / "agent.agent.md", PROBE)

    with echo_http_server((PROBE / "plugins" / "local-echo").resolve()):
        result = copilot.probe(package, BINDING)

    assert result.exit_code == 0, result.notes
    assert result.mcp_tools_offered == ["echohttp-echo_http", "echostdio-echo_stdio"], result.tools_offered_to_entry
    by_label = {parse_echo_result(item["result"]).get("label"): parse_echo_result(item["result"]) for item in result.mcp_results}
    assert set(by_label) == {"stdio", "http"}, result.mcp_results
    assert by_label["stdio"]["cwd"] == "${PROJECT_DIR}"  # no cwd field in the agent file configuration
    assert by_label["stdio"]["plugin_root_env"] is True and by_label["stdio"]["plugin_data_env"] is True
