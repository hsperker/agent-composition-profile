from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from ..model import Agent


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
