from pathlib import Path

import pytest

from agent_profile_compiler.model import McpServer
from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime.common import plugin_activation_assessment, source_semantic_features
from agent_profile_compiler.runtime.plugins import effective_server_config


ROOT = Path(__file__).parents[3]
PROBE = ROOT / "examples" / "runtime-probes" / "plugin-activation"


def test_activation_fixture_loads_with_plugin_root_on_each_server() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)

    agent = package.entry
    assert agent.name == "plugin-user"
    assert [server.name for server in agent.mcp_servers] == ["echostdio", "echohttp"]
    assert all(server.plugin_root == (PROBE / "plugins" / "local-echo").resolve() for server in agent.mcp_servers)


def test_stdio_placeholders_expand_once_and_reserved_env_is_injected(tmp_path: Path) -> None:
    root = tmp_path / "plugin"
    root.mkdir()
    server = McpServer(
        name="s",
        config={
            "type": "stdio",
            "command": "python",
            "args": ["${PLUGIN_ROOT}/servers/x.py", "${PLUGIN_DATA}/state", "${PLUGIN_ROOT}${PLUGIN_ROOT}"],
            "env": {"A": "${PLUGIN_DATA}/a", "B": "${PLUGIN_ROOT}"},
            "cwd": "${PLUGIN_ROOT}/servers",
        },
        plugin_root=root,
    )
    data = tmp_path / "data"

    config = effective_server_config(server, data_root=data)

    assert config["command"] == "python"
    assert config["args"] == [f"{root}/servers/x.py", f"{data}/state", f"{root}{root}"]
    assert config["env"] == {"A": f"{data}/a", "B": str(root), "PLUGIN_ROOT": str(root), "PLUGIN_DATA": str(data)}
    assert config["cwd"] == f"{root}/servers"
    assert data.is_dir()
    # The source configuration is untouched.
    assert server.config["args"][0] == "${PLUGIN_ROOT}/servers/x.py"


def test_relative_cwd_resolves_against_the_plugin_root(tmp_path: Path) -> None:
    server = McpServer(name="s", config={"type": "stdio", "command": "x", "cwd": "./bin"}, plugin_root=tmp_path)

    assert effective_server_config(server, data_root=tmp_path / "d")["cwd"] == str(tmp_path / "bin")


def test_http_servers_are_returned_unchanged(tmp_path: Path) -> None:
    config = {"type": "streamable-http", "url": "http://x/mcp", "headers": {"H": "${PLUGIN_ROOT}"}}
    server = McpServer(name="s", config=config, plugin_root=tmp_path)

    assert effective_server_config(server, data_root=tmp_path / "d") == config


def test_agents_with_plugins_carry_an_activation_finding() -> None:
    package = load_package(PROBE / "agent.agent.md", PROBE)

    assert "plugins.activation" in source_semantic_features(package.entry)
    assert plugin_activation_assessment(package.entry)["plugins.activation"][0] == "unverified"
