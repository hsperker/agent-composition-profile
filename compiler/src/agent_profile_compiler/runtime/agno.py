"""Agno runtime experiment."""

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


TARGET = "agno"


def _skills(agent):
    if not agent.all_skills:
        return None
    from agno.skills import LocalSkills, Skills

    return Skills(loaders=[LocalSkills(str(skill.root)) for skill in agent.all_skills])


def _mcp_tools(agent, data_root: Path):
    from agno.tools.mcp import MCPTools
    from mcp import StdioServerParameters

    tools = []
    losses: list[str] = []
    for server in agent.mcp_servers:
        config = effective_server_config(server, data_root=data_root)
        transport = config.pop("type")
        if transport in {"streamable-http", "sse"}:
            tools.append(
                MCPTools(
                    name=server.name,
                    url=config["url"],
                    transport=transport,
                    headers=config.get("headers"),
                )
            )
        elif transport == "stdio":
            tools.append(
                MCPTools(
                    name=server.name,
                    transport="stdio",
                    server_params=StdioServerParameters(
                        command=config["command"],
                        args=list(config.get("args", [])),
                        env=config.get("env"),
                        cwd=config.get("cwd"),
                    ),
                )
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
    from agno.agent import Agent
    from agno.team import Team

    models = binding.get("models", {})
    if not isinstance(models, Mapping):
        models = {}
    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    native_agents: dict[str, Agent] = {}
    native_skills: dict[str, Any] = {}
    native_tools: dict[str, list[Any]] = {}
    losses: dict[str, list[str]] = {}
    data_root = plugin_data_root(binding)

    for agent in package.agents.values():
        model = models.get(agent.name, binding.get("model"))
        if model is None:
            raise ValueError(f"Agno binding has no model for agent {agent.name!r}")
        skills = _skills(agent)
        mcp_tools, mcp_losses = _mcp_tools(agent, data_root)
        native_skills[agent.name] = skills
        native_tools[agent.name] = mcp_tools
        losses[agent.name] = mcp_losses
        native = Agent(
            name=agent.name,
            description=agent.description,
            instructions=agent.instructions,
            model=model,
            skills=skills,
            tools=mcp_tools or None,
            telemetry=False,
        )
        native_agents[agent.name] = native
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                agent.name,
                {
                    "native_type": f"{type(native).__module__}.{type(native).__name__}",
                    "skill_names": skills.get_skill_names() if skills else [],
                    "mcp_toolkits": len(mcp_tools),
                },
            )
        )

    teams: dict[str, Team] = {}
    for agent in package.agents.values():
        if not agent.delegate_names:
            continue
        team = Team(
            members=[native_agents[name] for name in agent.delegate_names],
            name=agent.name,
            description=agent.description,
            instructions=agent.instructions,
            model=native_agents[agent.name].model,
            skills=native_skills[agent.name],
            tools=native_tools[agent.name] or None,
            telemetry=False,
        )
        teams[agent.name] = team
        observations.append(
            RuntimeObservation(
                "team-constructed",
                agent.name,
                {
                    "mechanism": "team-member-collaboration",
                    "members": list(agent.delegate_names),
                },
            )
        )

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": ("preserved", "Agno Agent has a native name property."),
            "description": (
                "approximated",
                "Agno stores description but also injects it into generated model context, changing passive discovery metadata into prompt content.",
            ),
            "instructions": (
                "preserved",
                "The literal Markdown body is stored in Agent.instructions and sent in system context.",
            ),
            "skills": (
                ("preserved", "Agno's native Agent Skills implementation: catalog metadata in the system prompt, then get_skill_instructions delivers the full body on demand as a tool result, the dedicated tool activation pattern of the Agent Skills integration guide.")
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    "unsupported",
                    "Agno MCP configuration losses: " + "; ".join(losses[agent.name]),
                )
                if losses[agent.name]
                else (
                    (
                        "resolved",
                        "Each Agent Plugin MCP server becomes an agent-scoped native MCPTools toolkit with transport configuration preserved.",
                    )
                    if agent.plugins
                    else ("preserved", "The source agent declares no plugins.")
                )
            ),
            "delegates": (
                (
                    "approximated",
                    "Agno Team provides member collaboration and shared team execution, not a fresh bounded child call returning control to an Agent parent.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(
            capability_assessments(
                agent,
                binding,
                resolved_detail="The external binding attests the capability for the injected Agno Model.",
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
        metadata={"entry_name": package.entry_name, "teams": teams},
    )


def run(artifact: RuntimeArtifact, task: str, *, activate_plugins: bool = False) -> RuntimeRun:
    from agno.tools.mcp import MCPTools

    entry_name = str(artifact.metadata["entry_name"])
    agent = artifact.native_agents[entry_name]
    observations: list[RuntimeObservation] = []
    tool_servers: dict[str, str] = {}

    async def execute():
        # Agent.arun connects MCPTools toolkits itself (agno.agent._init.connect_mcp_tools)
        # and disconnects them afterwards; the discovered functions are read before release.
        response = await agent.arun(task, stream=False)
        return response

    if not activate_plugins:
        response = agent.run(task, stream=False)
    else:
        async def execute_with_discovery():
            toolkits = [tool for tool in (agent.tools or []) if isinstance(tool, MCPTools)]
            for toolkit in toolkits:
                try:
                    await toolkit.connect()
                except Exception as exc:  # Agent Plugins §7.2.2: report and continue
                    observations.append(
                        RuntimeObservation(
                            "mcp-activation-failed",
                            entry_name,
                            {"server": toolkit.name, "error": f"{type(exc).__name__}: {exc}"},
                        )
                    )
                    agent.tools.remove(toolkit)
                    continue
                names = sorted(toolkit.functions)
                tool_servers.update({name: toolkit.name for name in names})
                observations.append(
                    RuntimeObservation("mcp-tools-discovered", entry_name, {"server": toolkit.name, "tools": names})
                )
            return await execute()

        response = asyncio.run(execute_with_discovery())
        for execution in response.tools or []:
            if execution.tool_name in tool_servers:
                observations.append(
                    RuntimeObservation(
                        "mcp-tool-invoked",
                        entry_name,
                        {"server": tool_servers[execution.tool_name], "tool": execution.tool_name, "arguments": dict(execution.tool_args or {})},
                    )
                )
                observations.append(
                    RuntimeObservation(
                        "mcp-tool-result",
                        entry_name,
                        {"server": tool_servers[execution.tool_name], "tool": execution.tool_name, "result": str(execution.result)},
                    )
                )
    output = str(response.content)
    observation = RuntimeObservation("runtime-output", entry_name, {"result": output})
    observations.append(observation)
    artifact.observations.extend(observations)
    return RuntimeRun(output, tuple(observations))
