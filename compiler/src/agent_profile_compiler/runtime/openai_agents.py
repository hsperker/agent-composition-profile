"""OpenAI Agents SDK runtime experiment."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..model import CompatibilityReport, Package
from .common import assess_agent_semantics, capability_assessments, enforce_strict_runtime
from .model import RuntimeArtifact, RuntimeObservation, RuntimeRun
from .skills import SkillCatalog


TARGET = "openai-agents"


def _mcp_servers(agent):
    from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp

    native = []
    losses: list[str] = []
    for server in agent.mcp_servers:
        config = dict(server.config)
        transport = config.pop("type")
        if transport == "streamable-http":
            native.append(
                MCPServerStreamableHttp(
                    params={
                        "url": config["url"],
                        **({"headers": config["headers"]} if "headers" in config else {}),
                    },
                    name=server.name,
                )
            )
        elif transport == "sse":
            native.append(
                MCPServerSse(
                    params={
                        "url": config["url"],
                        **({"headers": config["headers"]} if "headers" in config else {}),
                    },
                    name=server.name,
                )
            )
        elif transport == "stdio":
            native.append(
                MCPServerStdio(
                    params={
                        "command": config["command"],
                        **({"args": config["args"]} if "args" in config else {}),
                        **({"env": config["env"]} if "env" in config else {}),
                        **({"cwd": config["cwd"]} if "cwd" in config else {}),
                    },
                    name=server.name,
                )
            )
        else:
            losses.append(f"{server.name}: unsupported transport {transport!r}")
    return native, losses


def build(
    package: Package,
    binding: Mapping[str, Any],
    *,
    strict: bool = True,
) -> RuntimeArtifact:
    from agents import Agent, function_tool

    models = binding.get("models", {})
    if not isinstance(models, Mapping):
        models = {}
    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    native_agents: dict[str, Agent] = {}
    mcp_losses: dict[str, list[str]] = {}

    def build_agent(name: str) -> Agent:
        if name in native_agents:
            return native_agents[name]
        source = package.agents[name]
        model = models.get(name, binding.get("model"))
        if model is None:
            raise ValueError(f"OpenAI Agents SDK binding has no model for agent {name!r}")
        catalog = SkillCatalog(name, source.all_skills)
        tools = []
        if catalog.metadata():
            def make_activate_skill(skill_catalog: SkillCatalog):
                def activate_skill(skill_name: str) -> str:
                    """Load one advertised Agent Skill's instructions."""
                    return skill_catalog.activate(skill_name)

                return activate_skill

            tools.append(
                function_tool(
                    make_activate_skill(catalog),
                    name_override="activate_skill",
                    description_override=(
                        "Activate one agent-private skill. Available metadata: "
                        + catalog.discovery_text()
                    ),
                )
            )
        for delegate_name in source.delegate_names:
            child = build_agent(delegate_name)
            tools.append(
                child.as_tool(
                    tool_name=delegate_name,
                    tool_description=package.agents[delegate_name].description,
                )
            )
        servers, losses = _mcp_servers(source)
        mcp_losses[name] = losses
        native = Agent(
            name=source.name,
            handoff_description=source.description,
            instructions=source.instructions,
            model=model,
            tools=tools,
            mcp_servers=servers,
        )
        native_agents[name] = native
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                name,
                {
                    "native_type": f"{type(native).__module__}.{type(native).__name__}",
                    "tool_names": [tool.name for tool in tools],
                    "mcp_servers": len(servers),
                },
            )
        )
        return native

    build_agent(package.entry_name)
    for name in package.agents:
        build_agent(name)

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": ("preserved", "Agent.name preserves native identity."),
            "description": (
                "preserved",
                "Agent.handoff_description is native model-visible selection metadata and also supplies the specialist tool description.",
            ),
            "instructions": (
                "preserved",
                "The literal Markdown body is Agent.instructions and is sent as system instructions on every model call.",
            ),
            "skills": (
                (
                    "approximated",
                    "A function tool discloses skill text on demand, but the result has tool-output authority instead of instruction authority.",
                )
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    "unsupported",
                    "OpenAI Agents SDK MCP mapping losses: " + "; ".join(mcp_losses[agent.name]),
                )
                if mcp_losses[agent.name]
                else (
                    (
                        "resolved",
                        "Agent Plugin MCP configuration expands into this Agent's native MCPServer objects; the plugin package wrapper is not retained.",
                    )
                    if agent.plugins
                    else ("preserved", "The source agent declares no plugins.")
                )
            ),
            "delegates": (
                (
                    "preserved",
                    "Agent.as_tool starts the specialist as a nested run with its own instructions/model and returns text without transferring the conversation.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(
            capability_assessments(
                agent,
                binding,
                resolved_detail="The external binding attests the capability for the injected Agents SDK Model.",
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
            "delegate_names": {
                agent.name: list(agent.delegate_names) for agent in package.agents.values()
            },
        },
    )


def run(artifact: RuntimeArtifact, task: str) -> RuntimeRun:
    from agents import Runner

    entry_name = str(artifact.metadata["entry_name"])
    result = Runner.run_sync(artifact.native_agents[entry_name], task)
    observations: list[RuntimeObservation] = []
    delegates = set(artifact.metadata["delegate_names"].get(entry_name, []))
    pending: dict[str, str] = {}
    for item in result.new_items:
        raw = getattr(item, "raw_item", None)
        name = raw.get("name") if isinstance(raw, dict) else getattr(raw, "name", None)
        if name in delegates and hasattr(raw, "arguments"):
            arguments = json.loads(raw.arguments)
            pending[getattr(raw, "call_id", name)] = name
            observations.append(
                RuntimeObservation(
                    "delegate-started",
                    entry_name,
                    {
                        "delegate": name,
                        "mechanism": "agent-as-tool",
                        "task": arguments.get("input", ""),
                    },
                )
            )
        call_id = raw.get("call_id") if isinstance(raw, dict) else getattr(raw, "call_id", None)
        if call_id in pending and hasattr(item, "output"):
            observations.append(
                RuntimeObservation(
                    "delegate-returned",
                    entry_name,
                    {"delegate": pending[call_id], "result": str(item.output)},
                )
            )
    output = str(result.final_output)
    observations.append(RuntimeObservation("runtime-output", entry_name, {"result": output}))
    artifact.observations.extend(observations)
    return RuntimeRun(output, tuple(observations))
