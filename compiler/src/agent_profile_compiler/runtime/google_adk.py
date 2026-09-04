"""Google Agent Development Kit runtime experiment."""

from __future__ import annotations

import keyword
import re
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
from .skills import SkillCatalog


TARGET = "google-adk"


def _adk_name(source_name: str) -> str:
    """Resolve profile identities to ADK's required Python identifiers."""

    candidate = re.sub(r"\W", "_", source_name)
    if not candidate or candidate[0].isdigit():
        candidate = f"agent_{candidate}"
    if keyword.iskeyword(candidate):
        candidate = f"agent_{candidate}"
    return candidate


def _literal_instruction(text: str):
    # A callable avoids ADK's `{state_key}` interpolation changing Markdown.
    def instruction(_context) -> str:
        return text

    return instruction


def _activate_skill_tool(catalog: SkillCatalog):
    def activate_skill(skill_name: str) -> str:
        """Load one advertised Agent Skill's instructions."""

        return catalog.activate(skill_name)

    activate_skill.__doc__ = (
        "Load one agent-private skill on demand. Available metadata: "
        + catalog.discovery_text()
    )
    return activate_skill


def _mcp_toolsets(agent):
    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import (
        SseConnectionParams,
        StdioConnectionParams,
        StreamableHTTPConnectionParams,
    )
    from mcp import StdioServerParameters

    toolsets = []
    losses: list[str] = []
    for server in agent.mcp_servers:
        config = dict(server.config)
        transport = config.pop("type")
        if transport == "streamable-http":
            connection = StreamableHTTPConnectionParams(
                url=config["url"], headers=config.get("headers")
            )
        elif transport == "sse":
            connection = SseConnectionParams(
                url=config["url"], headers=config.get("headers")
            )
        elif transport == "stdio":
            connection = StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=config["command"],
                    args=list(config.get("args", [])),
                    env=config.get("env"),
                    cwd=config.get("cwd"),
                )
            )
        else:
            losses.append(f"{server.name}: unsupported transport {transport!r}")
            continue
        toolsets.append(McpToolset(connection_params=connection, tool_name_prefix=server.name))
    return toolsets, losses


def build(
    package: Package,
    binding: Mapping[str, Any],
    *,
    strict: bool = True,
) -> RuntimeArtifact:
    from google.adk.agents import LlmAgent
    from google.adk.tools import AgentTool

    models = binding.get("models", {})
    if not isinstance(models, Mapping):
        models = {}
    source_to_native = {name: _adk_name(name) for name in package.agents}
    if len(set(source_to_native.values())) != len(source_to_native):
        raise ValueError("Google ADK name resolution produced an identity collision")

    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    native_agents: dict[str, LlmAgent] = {}
    mcp_losses: dict[str, list[str]] = {}

    def build_agent(name: str) -> LlmAgent:
        if name in native_agents:
            return native_agents[name]
        source = package.agents[name]
        model = models.get(name, binding.get("model"))
        if model is None:
            raise ValueError(f"Google ADK binding has no model for agent {name!r}")
        catalog = SkillCatalog(name, source.all_skills)
        tools: list[Any] = []
        if catalog.metadata():
            tools.append(_activate_skill_tool(catalog))
        toolsets, losses = _mcp_toolsets(source)
        mcp_losses[name] = losses
        tools.extend(toolsets)
        for delegate_name in source.delegate_names:
            tools.append(
                AgentTool(
                    build_agent(delegate_name),
                    skip_summarization=False,
                    include_plugins=False,
                )
            )
        native = LlmAgent(
            name=source_to_native[name],
            description=source.description,
            instruction=_literal_instruction(source.instructions),
            model=model,
            tools=tools,
        )
        native_agents[name] = native
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                name,
                {
                    "native_type": f"{type(native).__module__}.{type(native).__name__}",
                    "native_name": native.name,
                    "tool_count": len(tools),
                },
            )
        )
        return native

    build_agent(package.entry_name)
    for name in package.agents:
        build_agent(name)

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": (
                (
                    "preserved",
                    "The source name already satisfies ADK's Python-identifier constraint.",
                )
                if source_to_native[agent.name] == agent.name
                else (
                    "resolved",
                    f"ADK rejects {agent.name!r}; the adapter uses {source_to_native[agent.name]!r} and retains a bidirectional identity map.",
                )
            ),
            "description": (
                "preserved",
                "LlmAgent.description is native agent and AgentTool selection metadata.",
            ),
            "instructions": (
                "preserved",
                "A native instruction callback returns the Markdown literally on each run, avoiding ADK state-template interpolation.",
            ),
            "skills": (
                ("resolved", "The framework has no Agent Skills concept. The adapter supplies the dedicated tool activation pattern of the Agent Skills integration guide: catalog in the tool description, full body returned on demand as a tool result.")
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    "unsupported",
                    "Google ADK MCP configuration losses: " + "; ".join(mcp_losses[agent.name]),
                )
                if mcp_losses[agent.name]
                else (
                    (
                        "resolved",
                        "Agent Plugin MCP servers become agent-owned native McpToolset objects with transport configuration preserved.",
                    )
                    if agent.plugins
                    else ("preserved", "The source agent declares no plugins.")
                )
            ),
            "delegates": (
                (
                    "approximated",
                    "AgentTool is a bounded nested run, but it copies parent state into a fresh session and propagates child state deltas back.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(
            capability_assessments(
                agent,
                binding,
                resolved_detail="The external binding attests the capability for the injected ADK BaseLlm.",
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
            "source_to_native": source_to_native,
            "delegate_native_names": {
                name: [source_to_native[child] for child in agent.delegate_names]
                for name, agent in package.agents.items()
            },
        },
    )


def run(artifact: RuntimeArtifact, task: str) -> RuntimeRun:
    import asyncio

    from google.adk.runners import InMemoryRunner

    entry_name = str(artifact.metadata["entry_name"])
    runner = InMemoryRunner(agent=artifact.native_agents[entry_name])
    async def execute():
        try:
            return await runner.run_debug(task, quiet=True)
        finally:
            await runner.close()

    events = asyncio.run(execute())
    observations: list[RuntimeObservation] = []
    delegates = set(artifact.metadata["delegate_native_names"].get(entry_name, []))
    output = ""
    for event in events:
        content = getattr(event, "content", None)
        for part in getattr(content, "parts", None) or []:
            call = getattr(part, "function_call", None)
            if call and call.name in delegates:
                observations.append(
                    RuntimeObservation(
                        "delegate-started",
                        entry_name,
                        {
                            "delegate": call.name,
                            "mechanism": "agent-tool-shared-state",
                            "task": (call.args or {}).get("request", ""),
                        },
                    )
                )
            response = getattr(part, "function_response", None)
            if response and response.name in delegates:
                observations.append(
                    RuntimeObservation(
                        "delegate-returned",
                        entry_name,
                        {"delegate": response.name, "result": str(response.response)},
                    )
                )
            text = getattr(part, "text", None)
            if text and getattr(content, "role", None) == "model":
                output = text
    observations.append(RuntimeObservation("runtime-output", entry_name, {"result": output}))
    artifact.observations.extend(observations)
    return RuntimeRun(output, tuple(observations))
