"""CrewAI runtime experiment."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..model import CompatibilityReport, Package
from .common import assess_agent_semantics, capability_assessments, enforce_strict_runtime
from .model import RuntimeArtifact, RuntimeObservation, RuntimeRun


TARGET = "crewai"


def _mcp_configs(agent):
    from crewai.mcp.config import MCPServerHTTP, MCPServerSSE, MCPServerStdio

    mapped = []
    losses: list[str] = []
    for server in agent.mcp_servers:
        config = dict(server.config)
        transport = config.pop("type")
        if transport == "streamable-http":
            mapped.append(
                MCPServerHTTP(
                    url=config["url"],
                    headers=config.get("headers"),
                    streamable=True,
                )
            )
        elif transport == "sse":
            mapped.append(MCPServerSSE(url=config["url"], headers=config.get("headers")))
        elif transport == "stdio":
            mapped.append(
                MCPServerStdio(
                    command=config["command"],
                    args=list(config.get("args", [])),
                    env=config.get("env"),
                )
            )
            if "cwd" in config:
                losses.append(f"{server.name}: CrewAI MCPServerStdio has no cwd field")
        else:
            losses.append(f"{server.name}: unsupported transport {transport!r}")
    return mapped, losses


def build(
    package: Package,
    binding: Mapping[str, Any],
    *,
    strict: bool = True,
) -> RuntimeArtifact:
    from crewai import Agent as CrewAgent
    from crewai import Crew, Process
    from crewai.skills.parser import load_skill_metadata

    models = binding.get("models", {})
    if not isinstance(models, Mapping):
        models = {}
    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    native_agents: dict[str, CrewAgent] = {}
    mcp_losses: dict[str, list[str]] = {}

    for agent in package.agents.values():
        model = models.get(agent.name, binding.get("model"))
        if model is None:
            raise ValueError(f"CrewAI binding has no model for agent {agent.name!r}")
        mcps, losses = _mcp_configs(agent)
        mcp_losses[agent.name] = losses
        native = CrewAgent(
            role=agent.name,
            goal=agent.description,
            backstory=agent.instructions,
            llm=model,
            allow_delegation=bool(agent.delegate_names),
            skills=[load_skill_metadata(skill.root) for skill in agent.all_skills] or None,
            mcps=mcps or None,
            verbose=False,
        )
        native_agents[agent.name] = native
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                agent.name,
                {
                    "native_type": f"{type(native).__module__}.{type(native).__name__}",
                    "role": native.role,
                    "skill_names": [skill.frontmatter.name for skill in (native.skills or [])],
                    "mcp_count": len(native.mcps or []),
                    "allow_delegation": native.allow_delegation,
                },
            )
        )

    crew = Crew(
        name=f"{package.entry_name}-crew",
        agents=list(native_agents.values()),
        tasks=[],
        process=Process.sequential,
        verbose=False,
    )

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": (
                "approximated",
                "CrewAI has a role string rather than a stable machine-readable agent name; the source name is placed in role.",
            ),
            "description": (
                "approximated",
                "CrewAI goal is model-visible prompt content, not passive discovery/routing metadata.",
            ),
            "instructions": (
                "approximated",
                "The Markdown body is placed in backstory and embedded in CrewAI's generated prompt template rather than a literal persistent instruction field.",
            ),
            "skills": (
                (
                    "preserved",
                    "CrewAI 1.15 loads Agent Skills natively with progressive disclosure.",
                )
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    "unsupported",
                    "CrewAI cannot preserve all Agent Plugin MCP settings: "
                    + "; ".join(mcp_losses[agent.name]),
                )
                if mcp_losses[agent.name]
                else (
                    (
                        "resolved",
                        "Agent Plugin MCP servers are mechanically expanded into this agent's native mcps list; plugin packaging itself is not retained.",
                    )
                    if agent.plugins
                    else ("preserved", "The source agent declares no plugins.")
                )
            ),
            "delegates": (
                (
                    "approximated",
                    "CrewAI delegation is team-member collaboration with task/context fields inside a Crew, not the profile's fresh text-in/text-out child invocation.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(
            capability_assessments(
                agent,
                binding,
                resolved_detail="The external binding attests the capability for the injected CrewAI BaseLLM.",
            )
        )
        assess_agent_semantics(report, agent, assessments)

    if strict:
        enforce_strict_runtime(report)
    return RuntimeArtifact(
        target=TARGET,
        native_agents=native_agents,
        report=report,
        observations=observations,
        metadata={"entry_name": package.entry_name, "crew": crew},
    )


def run(artifact: RuntimeArtifact, task: str) -> RuntimeRun:
    entry_name = str(artifact.metadata["entry_name"])
    start = len(artifact.observations)
    response = artifact.native_agents[entry_name].kickoff(task)
    output = str(getattr(response, "raw", response))
    artifact.observations.append(
        RuntimeObservation("runtime-output", entry_name, {"result": output})
    )
    return RuntimeRun(output, tuple(artifact.observations[start:]))
