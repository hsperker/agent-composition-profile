"""PydanticAI runtime experiment."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..model import CompatibilityReport, Package
from .common import assess_agent_semantics, capability_assessments, enforce_strict_runtime
from .model import RuntimeArtifact, RuntimeObservation, RuntimeRun
from .skills import SkillCatalog


TARGET = "pydantic-ai"


def _mcp_toolsets(agent):
    from fastmcp.client.transports import SSETransport, StdioTransport, StreamableHttpTransport
    from pydantic_ai.mcp import MCPToolset

    toolsets = []
    losses: list[str] = []
    for server in agent.mcp_servers:
        config = dict(server.config)
        transport = config.pop("type")
        if transport == "streamable-http":
            native_transport = StreamableHttpTransport(
                config["url"], headers=config.get("headers")
            )
        elif transport == "sse":
            native_transport = SSETransport(config["url"], headers=config.get("headers"))
        elif transport == "stdio":
            native_transport = StdioTransport(
                command=config["command"],
                args=list(config.get("args", [])),
                env=config.get("env"),
                cwd=config.get("cwd"),
            )
        else:
            losses.append(f"{server.name}: unsupported transport {transport!r}")
            continue
        toolsets.append(MCPToolset(native_transport, id=server.name))
    return toolsets, losses


def _skill_tool(catalog: SkillCatalog):
    from pydantic_ai import Tool

    def activate_skill(skill_name: str) -> str:
        """Load one advertised Agent Skill's instructions."""

        return catalog.activate(skill_name)

    return Tool(
        activate_skill,
        name="activate_skill",
        description=(
            "Load one agent-private skill on demand. Available metadata: "
            + catalog.discovery_text()
        ),
    )


def build(
    package: Package,
    binding: Mapping[str, Any],
    *,
    strict: bool = True,
) -> RuntimeArtifact:
    from pydantic_ai import Agent, Tool

    models = binding.get("models", {})
    if not isinstance(models, Mapping):
        models = {}
    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    runtime_trace: list[RuntimeObservation] = []
    native_agents: dict[str, Agent] = {}
    mcp_losses: dict[str, list[str]] = {}

    def build_agent(name: str) -> Agent:
        if name in native_agents:
            return native_agents[name]
        source = package.agents[name]
        model = models.get(name, binding.get("model"))
        if model is None:
            raise ValueError(f"PydanticAI binding has no model for agent {name!r}")
        catalog = SkillCatalog(name, source.all_skills)
        tools = []
        if catalog.metadata():
            tools.append(_skill_tool(catalog))
        for delegate_name in source.delegate_names:
            child = build_agent(delegate_name)

            def make_delegate(child_name: str, child_agent: Agent):
                async def delegate(task: str) -> str:
                    runtime_trace.append(
                        RuntimeObservation(
                            "delegate-started",
                            name,
                            {
                                "delegate": child_name,
                                "mechanism": "adapter-function-tool",
                                "task": task,
                            },
                        )
                    )
                    result = str((await child_agent.run(task)).output)
                    runtime_trace.append(
                        RuntimeObservation(
                            "delegate-returned",
                            name,
                            {"delegate": child_name, "result": result},
                        )
                    )
                    return result

                return delegate

            tools.append(
                Tool(
                    make_delegate(delegate_name, child),
                    name=delegate_name,
                    description=package.agents[delegate_name].description,
                )
            )
        toolsets, losses = _mcp_toolsets(source)
        mcp_losses[name] = losses
        native = Agent(
            model,
            name=source.name,
            description=source.description,
            instructions=source.instructions,
            tools=tools,
            toolsets=toolsets,
        )
        native_agents[name] = native
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                name,
                {
                    "native_type": f"{type(native).__module__}.{type(native).__name__}",
                    "function_tools": sorted(native._function_toolset.tools),
                    "mcp_toolsets": len(toolsets),
                },
            )
        )
        return native

    build_agent(package.entry_name)
    for name in package.agents:
        build_agent(name)

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": ("preserved", "PydanticAI Agent.name preserves the source identity."),
            "description": (
                "preserved",
                "PydanticAI Agent.description stores native human-readable agent metadata.",
            ),
            "instructions": (
                "preserved",
                "The literal Markdown is registered as persistent native Agent instructions.",
            ),
            "skills": (
                (
                    "approximated",
                    "A function tool progressively reveals skill text, but the result has tool-output instead of instruction authority.",
                )
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    "unsupported",
                    "PydanticAI MCP configuration losses: " + "; ".join(mcp_losses[agent.name]),
                )
                if mcp_losses[agent.name]
                else (
                    (
                        "resolved",
                        "Agent Plugin MCP servers become agent-scoped MCPToolset objects with explicit FastMCP transports.",
                    )
                    if agent.plugins
                    else ("preserved", "The source agent declares no plugins.")
                )
            ),
            "delegates": (
                (
                    "approximated",
                    "PydanticAI has no agent relationship primitive; the adapter authors Tool objects that run a child Agent and return text. That is an adapter-chosen orchestration policy, not a framework semantic.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(
            capability_assessments(
                agent,
                binding,
                resolved_detail="The external binding attests the capability for the injected PydanticAI Model.",
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
        metadata={
            "entry_name": package.entry_name,
            "runtime_trace": runtime_trace,
        },
    )


def run(artifact: RuntimeArtifact, task: str) -> RuntimeRun:
    entry_name = str(artifact.metadata["entry_name"])
    trace: list[RuntimeObservation] = artifact.metadata["runtime_trace"]
    start = len(trace)
    result = artifact.native_agents[entry_name].run_sync(task)
    output = str(result.output)
    observation = RuntimeObservation("runtime-output", entry_name, {"result": output})
    observations = tuple(trace[start:]) + (observation,)
    artifact.observations.extend(observations)
    return RuntimeRun(output, observations)
