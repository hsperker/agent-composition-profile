from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..model import Agent, McpServer


_PLACEHOLDERS = ("${PLUGIN_ROOT}", "${PLUGIN_DATA}")


def _expand(value: str, plugin_root: str, data_root: str) -> str:
    """Agent Plugins §9.2: one non-recursive textual replacement of each placeholder."""

    out: list[str] = []
    i = 0
    while i < len(value):
        if value.startswith("${PLUGIN_ROOT}", i):
            out.append(plugin_root)
            i += len("${PLUGIN_ROOT}")
        elif value.startswith("${PLUGIN_DATA}", i):
            out.append(data_root)
            i += len("${PLUGIN_DATA}")
        else:
            out.append(value[i])
            i += 1
    return "".join(out)


def plugin_data_root(binding: Mapping[str, Any]) -> Path:
    """PLUGIN_DATA directory: from the binding, else a fresh temporary directory."""

    import tempfile

    configured = binding.get("plugin_data_root")
    if configured:
        return Path(str(configured))
    return Path(tempfile.mkdtemp(prefix="acp-plugin-data-"))


def effective_server_config(server: McpServer, *, data_root: Path) -> dict[str, Any]:
    """Return the client-facing configuration for one Agent Plugin MCP server.

    HTTP servers pass through unchanged. For stdio servers this applies Agent
    Plugins §9: placeholders are expanded in args, env values, and cwd (never in
    the command or keys), a ./ cwd resolves against the plugin root, and the
    reserved PLUGIN_ROOT and PLUGIN_DATA variables are provided to the process.
    """

    config = copy.deepcopy(dict(server.config))
    if config.get("type") != "stdio":
        return config
    if server.plugin_root is None:
        raise ValueError(f"{server.name}: stdio server has no plugin root for placeholder expansion")
    data_root.mkdir(parents=True, exist_ok=True)
    root = str(server.plugin_root)
    data = str(data_root)
    if "args" in config:
        config["args"] = [_expand(arg, root, data) for arg in config["args"]]
    env = {key: _expand(value, root, data) for key, value in dict(config.get("env") or {}).items()}
    env["PLUGIN_ROOT"] = root
    env["PLUGIN_DATA"] = data
    config["env"] = env
    if "cwd" in config:
        cwd = _expand(config["cwd"], root, data)
        if cwd.startswith("./"):
            cwd = str(server.plugin_root / cwd[2:])
        config["cwd"] = cwd
    return config


@dataclass(frozen=True)
class PluginServer:
    owner: str
    plugin: str
    name: str
    config: Mapping[str, Any]


class PluginCatalog:
    """Agent-owned view of every MCP component contributed by its plugins."""

    def __init__(self, owner: str, servers: list[PluginServer]) -> None:
        self.owner = owner
        self._servers = {server.name: server for server in servers}

    @classmethod
    def from_agent(cls, agent: Agent) -> PluginCatalog:
        servers = [
            PluginServer(
                owner=agent.name,
                plugin=plugin.name,
                name=server.name,
                config=copy.deepcopy(dict(server.config)),
            )
            for plugin in agent.plugins
            for server in plugin.mcp_servers
        ]
        return cls(agent.name, servers)

    def server(self, name: str) -> PluginServer:
        try:
            return self._servers[name]
        except KeyError as exc:
            raise KeyError(f"{self.owner}: unknown plugin MCP server {name!r}") from exc

    def servers(self) -> tuple[PluginServer, ...]:
        return tuple(self._servers.values())
