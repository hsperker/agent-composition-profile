"""LlamaIndex runtime experiment."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..model import CompatibilityReport, Package
from .common import (
    assess_agent_semantics,
    capability_assessments,
    enforce_strict_runtime,
    plugin_activation_assessment,
    skill_durability_assessment,
)
from .model import RuntimeArtifact, RuntimeObservation, RuntimeRun
from .plugins import effective_server_config, plugin_data_root
from .skills import SkillCatalog


TARGET = "llamaindex"


def _mcp_clients(agent, data_root: Path):
    from llama_index.tools.mcp import BasicMCPClient

    clients = []
    losses: list[str] = []
    for server in agent.mcp_servers:
        config = effective_server_config(server, data_root=data_root)
        transport = config.pop("type")
        if transport in {"streamable-http", "sse"}:
            clients.append(
                (
                    server.name,
                    BasicMCPClient(
                        config["url"],
                        headers=config.get("headers"),
                    ),
                )
            )
        elif transport == "stdio":
            clients.append(
                (
                    server.name,
                    BasicMCPClient(
                        config["command"],
                        args=list(config.get("args", [])),
                        env=config.get("env"),
                    ),
                )
            )
            # cwd is always set after Agent Plugins §7.2.1 defaulting; BasicMCPClient cannot honor it.
            losses.append(
                f"{server.name}: BasicMCPClient has no cwd parameter, so neither a declared cwd "
                "nor the required plugin-root default can be honored"
            )
        else:
            losses.append(f"{server.name}: unsupported transport {transport!r}")
    return clients, losses


async def _activate_plugins(agent_name, clients, observations, tool_servers) -> list[Any]:
    """Handshake with each plugin MCP server through McpToolSpec and load its tools.

    Runs inside the same event loop as the agent run: BasicMCPClient keeps an
    httpx client whose connections are bound to the loop that first used it.
    """

    from llama_index.tools.mcp import McpToolSpec

    tools: list[Any] = []
    for server_name, client in clients:
        try:
            loaded = await McpToolSpec(client).to_tool_list_async()
        except Exception as exc:  # Agent Plugins §7.2.2: report and continue
            observations.append(
                RuntimeObservation(
                    "mcp-activation-failed",
                    agent_name,
                    {"server": server_name, "error": f"{type(exc).__name__}: {exc}"},
                )
            )
            continue
        names = [tool.metadata.name for tool in loaded]
        tool_servers.update({name: server_name for name in names})
        tools.extend(loaded)
        observations.append(
            RuntimeObservation("mcp-tools-discovered", agent_name, {"server": server_name, "tools": names})
        )
    return tools


def build(
    package: Package,
    binding: Mapping[str, Any],
    *,
    strict: bool = True,
) -> RuntimeArtifact:
    from llama_index.core.agent.workflow import AgentWorkflow, FunctionAgent
    from llama_index.core.tools import FunctionTool

    models = binding.get("models", {})
    if not isinstance(models, Mapping):
        models = {}
    activate = bool(binding.get("activate_plugins"))
    data_root = plugin_data_root(binding)
    named_clients: dict[str, list[tuple[str, Any]]] = {}
    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    native_agents: dict[str, FunctionAgent] = {}
    mcp_clients: dict[str, list[Any]] = {}
    mcp_losses: dict[str, list[str]] = {}

    for agent in package.agents.values():
        model = models.get(agent.name, binding.get("model"))
        if model is None:
            raise ValueError(f"LlamaIndex binding has no model for agent {agent.name!r}")
        catalog = SkillCatalog(agent.name, agent.all_skills)
        tools = []
        if catalog.metadata():
            def make_activate_skill(skill_catalog: SkillCatalog):
                def activate_skill(skill_name: str) -> str:
                    """Load one advertised Agent Skill's instructions."""
                    return skill_catalog.activate(skill_name)

                return activate_skill

            tools.append(
                FunctionTool.from_defaults(
                    make_activate_skill(catalog),
                    name="activate_skill",
                    description=(
                        "Activate one skill from this agent's catalog. Available metadata: "
                        + catalog.discovery_text()
                    ),
                )
            )
        clients, losses = _mcp_clients(agent, data_root)
        mcp_clients[agent.name] = [client for _, client in clients]
        mcp_losses[agent.name] = losses
        if activate and clients:
            named_clients[agent.name] = clients
        native = FunctionAgent(
            name=agent.name,
            description=agent.description,
            system_prompt=agent.instructions,
            tools=tools,
            can_handoff_to=list(agent.delegate_names),
            llm=model,
            streaming=False,
        )
        native_agents[agent.name] = native
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                agent.name,
                {
                    "native_type": f"{type(native).__module__}.{type(native).__name__}",
                    "handoff_targets": list(native.can_handoff_to),
                    "mcp_clients": len(clients),
                },
            )
        )

    workflow = AgentWorkflow(
        agents=list(native_agents.values()),
        root_agent=package.entry_name,
    )

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": ("preserved", "FunctionAgent has a native name property."),
            "description": (
                "preserved",
                "FunctionAgent has native description metadata used by AgentWorkflow routing.",
            ),
            "instructions": (
                "preserved",
                "The literal Markdown body is FunctionAgent.system_prompt.",
            ),
            "skills": (
                ("resolved", "The framework has no Agent Skills concept. The adapter supplies the dedicated tool activation pattern of the Agent Skills integration guide: catalog in the tool description, full body returned on demand as a tool result.")
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    (
                        "resolved",
                        "Each plugin MCP server is activated at run start: BasicMCPClient performs the handshake and McpToolSpec attaches its tools to this FunctionAgent; the plugin wrapper is not retained.",
                    )
                    if activate
                    else (
                        "unsupported",
                        "A native BasicMCPClient can preserve connection configuration, but tools cannot be attached to FunctionAgent until an activation handshake succeeds. The fixture endpoint is unavailable.",
                    )
                )
                if agent.plugins
                else ("preserved", "The source agent declares no plugins.")
            ),
            "delegates": (
                (
                    "approximated",
                    "AgentWorkflow can_handoff_to transfers active control through shared workflow state instead of returning a bounded child result to the parent.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        if mcp_losses[agent.name]:
            assessments["plugins"] = (
                "unsupported",
                "LlamaIndex MCP configuration losses: " + "; ".join(mcp_losses[agent.name]),
            )
        assessments.update(
            capability_assessments(
                agent,
                binding,
                resolved_detail="The external binding attests the capability for the injected LlamaIndex LLM.",
            )
        )
        assessments.update(skill_durability_assessment(agent))
        assessments.update(plugin_activation_assessment(agent))
        assess_agent_semantics(report, agent, assessments)

    if strict:
        enforce_strict_runtime(report)
    return RuntimeArtifact(
        target=TARGET,
        native_agents=native_agents,
        report=report,
        observations=observations,
        metadata={
            "entry_name": package.entry_name,
            "workflow": workflow,
            "mcp_clients": mcp_clients,
            "mcp_named_clients": named_clients,
        },
    )


def run(artifact: RuntimeArtifact, task: str, *, activate_plugins: bool = False) -> RuntimeRun:
    from llama_index.core.agent.workflow import ToolCall, ToolCallResult

    entry_name = str(artifact.metadata["entry_name"])
    agent = artifact.native_agents[entry_name]
    tool_servers: dict[str, str] = {}
    observations: list[RuntimeObservation] = []

    async def invoke():
        if activate_plugins:
            clients = artifact.metadata.get("mcp_named_clients", {}).get(entry_name, [])
            loaded = await _activate_plugins(entry_name, clients, observations, tool_servers)
            agent.tools = [*(agent.tools or []), *loaded]
        handler = agent.run(task)
        async for event in handler.stream_events():
            if isinstance(event, ToolCall) and event.tool_name in tool_servers:
                observations.append(
                    RuntimeObservation(
                        "mcp-tool-invoked",
                        entry_name,
                        {"server": tool_servers[event.tool_name], "tool": event.tool_name, "arguments": dict(event.tool_kwargs)},
                    )
                )
            if isinstance(event, ToolCallResult) and event.tool_name in tool_servers:
                observations.append(
                    RuntimeObservation(
                        "mcp-tool-result",
                        entry_name,
                        {"server": tool_servers[event.tool_name], "tool": event.tool_name, "result": str(event.tool_output.content)},
                    )
                )
        return await handler

    response = asyncio.run(invoke())
    output = str(response)
    observation = RuntimeObservation("runtime-output", entry_name, {"result": output})
    artifact.observations.append(observation)
    return RuntimeRun(output, tuple(observations) + (observation,))
