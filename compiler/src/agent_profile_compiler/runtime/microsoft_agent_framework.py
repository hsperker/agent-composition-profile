"""Microsoft Agent Framework runtime experiment."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
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


TARGET = "microsoft-agent-framework"


def _skills_provider(agent):
    if not agent.all_skills:
        return None
    from agent_framework import SkillsProvider

    return SkillsProvider.from_paths(
        [str(skill.root) for skill in agent.all_skills],
        disable_load_skill_approval=True,
        disable_read_skill_resource_approval=True,
    )


def _header_provider(headers: Mapping[str, str]):
    def provide(_context: dict[str, Any]) -> dict[str, str]:
        return dict(headers)

    return provide


def _mcp_tools(agent):
    from agent_framework import MCPStdioTool, MCPStreamableHTTPTool

    tools = []
    losses: list[str] = []
    for server in agent.mcp_servers:
        config = dict(server.config)
        transport = config.pop("type")
        if transport == "streamable-http":
            kwargs: dict[str, Any] = {}
            if config.get("headers"):
                kwargs["header_provider"] = _header_provider(config["headers"])
            tools.append(
                MCPStreamableHTTPTool(
                    name=server.name,
                    url=config["url"],
                    tool_name_prefix=server.name,
                    **kwargs,
                )
            )
        elif transport == "stdio":
            tools.append(
                MCPStdioTool(
                    name=server.name,
                    command=config["command"],
                    tool_name_prefix=server.name,
                    args=list(config.get("args", [])),
                    env=config.get("env"),
                    cwd=config.get("cwd"),
                )
            )
        elif transport == "sse":
            losses.append(
                f"{server.name}: SDK 1.17.0 has streamable HTTP and WebSocket clients but no legacy SSE client"
            )
        else:
            losses.append(f"{server.name}: unsupported transport {transport!r}")
    return tools, losses


def build(
    package: Package,
    binding: Mapping[str, Any],
    *,
    strict: bool = True,
) -> RuntimeArtifact:
    from agent_framework import Agent

    clients = binding.get("models", {})
    if not isinstance(clients, Mapping):
        clients = {}
    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    native_agents: dict[str, Agent] = {}
    mcp_losses: dict[str, list[str]] = {}

    def build_agent(name: str) -> Agent:
        if name in native_agents:
            return native_agents[name]
        source = package.agents[name]
        client = clients.get(name, binding.get("model"))
        if client is None:
            raise ValueError(f"Microsoft Agent Framework binding has no client for agent {name!r}")
        provider = _skills_provider(source)
        mcp_tools, losses = _mcp_tools(source)
        mcp_losses[name] = losses
        delegate_tools = [
            build_agent(delegate_name).as_tool(
                description=package.agents[delegate_name].description,
                propagate_session=False,
            )
            for delegate_name in source.delegate_names
        ]
        native = Agent(
            client,
            name=source.name,
            description=source.description,
            instructions=source.instructions,
            tools=[*delegate_tools, *mcp_tools],
            context_providers=[provider] if provider else None,
        )
        native_agents[name] = native
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                name,
                {
                    "native_type": f"{type(native).__module__}.{type(native).__name__}",
                    "delegate_tools": [tool.name for tool in delegate_tools],
                    "mcp_tools": len(mcp_tools),
                    "skills_provider": provider is not None,
                },
            )
        )
        return native

    build_agent(package.entry_name)
    for name in package.agents:
        build_agent(name)

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": ("preserved", "Agent.name preserves the source identity."),
            "description": (
                "preserved",
                "Agent.description is native discovery metadata and supplies agent-tool selection text.",
            ),
            "instructions": (
                "preserved",
                "The Markdown is stored as native Agent instructions and passed through chat options to the client on every run.",
            ),
            "skills": (
                ("preserved", "SkillsProvider is a native Agent Skills implementation: catalog metadata first, then load_skill delivers the full body on demand as a tool result, the dedicated tool activation pattern of the Agent Skills integration guide. The adapter disables the provider's default approval gate on load_skill and read_skill_resource, which is host policy rather than a semantic change.")
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    "unsupported",
                    "Microsoft Agent Framework MCP configuration losses: "
                    + "; ".join(mcp_losses[agent.name]),
                )
                if mcp_losses[agent.name]
                else (
                    (
                        "resolved",
                        "Agent Plugin MCP servers become agent-owned MCP tools with the configured transport and lifecycle.",
                    )
                    if agent.plugins
                    else ("preserved", "The source agent declares no plugins.")
                )
            ),
            "delegates": (
                (
                    "preserved",
                    "Agent.as_tool(propagate_session=False) is a native bounded child run with an independent session that returns text to the caller.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(
            capability_assessments(
                agent,
                binding,
                resolved_detail="The external binding attests the capability for the injected chat client.",
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
            "delegate_names": {
                agent.name: list(agent.delegate_names) for agent in package.agents.values()
            },
        },
    )


def run(artifact: RuntimeArtifact, task: str) -> RuntimeRun:
    entry_name = str(artifact.metadata["entry_name"])
    response = asyncio.run(artifact.native_agents[entry_name].run(task))
    delegates = set(artifact.metadata["delegate_names"].get(entry_name, []))
    observations: list[RuntimeObservation] = []
    pending: dict[str, str] = {}
    for message in response.messages:
        for content in message.contents:
            if content.type == "function_call" and content.name in delegates:
                pending[content.call_id or content.name] = content.name
                arguments = content.arguments if isinstance(content.arguments, Mapping) else {}
                observations.append(
                    RuntimeObservation(
                        "delegate-started",
                        entry_name,
                        {
                            "delegate": content.name,
                            "mechanism": "agent-as-tool-isolated-session",
                            "task": arguments.get("task", ""),
                        },
                    )
                )
            if content.type == "function_result" and content.call_id in pending:
                observations.append(
                    RuntimeObservation(
                        "delegate-returned",
                        entry_name,
                        {
                            "delegate": pending[content.call_id],
                            "result": str(content.result),
                        },
                    )
                )
    output = response.text
    observations.append(RuntimeObservation("runtime-output", entry_name, {"result": output}))
    artifact.observations.extend(observations)
    return RuntimeRun(output, tuple(observations))
