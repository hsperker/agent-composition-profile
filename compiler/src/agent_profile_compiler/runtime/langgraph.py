"""LangChain/LangGraph runtime experiment."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from ..model import CompatibilityReport, Package
from .common import assess_agent_semantics, enforce_strict_runtime, plugin_activation_assessment, skill_durability_assessment
from .model import RuntimeArtifact, RuntimeObservation, RuntimeRun
from .plugins import effective_server_config, plugin_data_root
from .skills import SkillCatalog


TARGET = "langgraph"


def _capability_assessments(agent, binding: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    capabilities = binding.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        capabilities = {}
    assessments: dict[str, tuple[str, str]] = {}
    for capability in sorted(agent.requires):
        if capabilities.get(capability) is True:
            assessments[f"model.requires.{capability}"] = (
                "resolved",
                "The external binding explicitly attests this capability for the injected LangChain model.",
            )
        else:
            assessments[f"model.requires.{capability}"] = (
                "unsupported",
                f"The binding does not attest required capability {capability!r}.",
            )
    for capability in sorted(agent.prefers):
        if capabilities.get(capability) is True:
            assessments[f"model.prefers.{capability}"] = (
                "resolved",
                "The external binding explicitly attests this preferred capability.",
            )
        else:
            assessments[f"model.prefers.{capability}"] = (
                "omitted-preference",
                f"The binding does not attest preferred capability {capability!r}.",
            )
    return assessments


def _connection(config: dict[str, Any]) -> dict[str, Any]:
    """Map one Agent Plugins MCP entry to a langchain-mcp-adapters connection."""

    transport = config["type"]
    if transport == "stdio":
        connection: dict[str, Any] = {"transport": "stdio", "command": config["command"], "args": list(config.get("args", []))}
        if config.get("env"):
            connection["env"] = dict(config["env"])
        if config.get("cwd"):
            connection["cwd"] = config["cwd"]
        return connection
    if transport in {"streamable-http", "sse"}:
        connection = {"transport": "streamable_http" if transport == "streamable-http" else "sse", "url": config["url"]}
        if config.get("headers"):
            connection["headers"] = dict(config["headers"])
        return connection
    raise ValueError(f"unsupported transport {transport!r}")


def _activate_plugins(source, data_root, observations, tool_servers) -> tuple[list[Any], list[str]]:
    """Connect each plugin MCP server through langchain-mcp-adapters and load its tools."""

    from langchain_mcp_adapters.client import MultiServerMCPClient

    tools: list[Any] = []
    failures: list[str] = []
    for server in source.mcp_servers:
        config = effective_server_config(server, data_root=data_root)
        client = MultiServerMCPClient({server.name: _connection(config)})
        try:
            loaded = asyncio.run(client.get_tools(server_name=server.name))
        except Exception as exc:  # Agent Plugins §7.2.2: report and continue
            failures.append(f"{server.name}: {type(exc).__name__}: {exc}")
            observations.append(
                RuntimeObservation(
                    "mcp-activation-failed",
                    source.name,
                    {"server": server.name, "error": f"{type(exc).__name__}: {exc}"},
                )
            )
            continue
        names = [tool.name for tool in loaded]
        tool_servers.update({name: server.name for name in names})
        tools.extend(loaded)
        observations.append(
            RuntimeObservation("mcp-tools-discovered", source.name, {"server": server.name, "tools": names})
        )
    return tools, failures


def build(
    package: Package,
    binding: Mapping[str, Any],
    *,
    strict: bool = True,
) -> RuntimeArtifact:
    from langchain.agents import create_agent
    from langchain_core.tools import StructuredTool

    models = binding.get("models", {})
    if not isinstance(models, Mapping):
        models = {}
    activate = bool(binding.get("activate_plugins"))
    data_root = plugin_data_root(binding)
    tool_servers: dict[str, str] = {}
    activation_failures: dict[str, list[str]] = {}

    report = CompatibilityReport(target=TARGET, source_entry=package.entry_name)
    observations: list[RuntimeObservation] = []
    native_agents: dict[str, Any] = {}
    skill_catalogs = {
        agent.name: SkillCatalog(agent.name, agent.all_skills)
        for agent in package.agents.values()
    }
    referenced = {
        delegate
        for agent in package.agents.values()
        for delegate in agent.delegate_names
    }

    def build_agent(name: str):
        if name in native_agents:
            return native_agents[name]
        source = package.agents[name]
        tools: list[Any] = []

        catalog = skill_catalogs[name]
        if catalog.metadata():
            def activate_skill(skill_name: str, *, _catalog=catalog) -> str:
                """Load one advertised Agent Skill's full instructions by name."""
                return _catalog.activate(skill_name)

            tools.append(
                StructuredTool.from_function(
                    activate_skill,
                    name="activate_skill",
                    description=(
                        "Activate one skill from this agent's catalog. Available metadata: "
                        + catalog.discovery_text()
                    ),
                )
            )

        for delegate_name in source.delegate_names:
            delegate_graph = build_agent(delegate_name)
            delegate = package.agents[delegate_name]

            def invoke_delegate(
                task: str,
                *,
                _parent=name,
                _delegate=delegate,
                _graph=delegate_graph,
            ) -> str:
                """Run a specialist on a bounded task and return its text result."""
                observations.append(
                    RuntimeObservation(
                        "delegate-started",
                        _parent,
                        {
                            "delegate": _delegate.name,
                            "mechanism": "agent-as-tool",
                            "task": task,
                        },
                    )
                )
                result = _graph.invoke({"messages": [{"role": "user", "content": task}]})
                output = _message_text(result["messages"][-1])
                observations.append(
                    RuntimeObservation(
                        "delegate-returned",
                        _parent,
                        {"delegate": _delegate.name, "result": output},
                    )
                )
                return output

            tools.append(
                StructuredTool.from_function(
                    invoke_delegate,
                    name=delegate.name,
                    description=delegate.description,
                )
            )

        if activate and source.mcp_servers:
            mcp_tools, failures = _activate_plugins(source, data_root, observations, tool_servers)
            activation_failures[name] = failures
            tools.extend(mcp_tools)

        model = models.get(name)
        if model is None:
            # A concrete model belongs to the target binding, never the profile.
            model = binding.get("model")
        if model is None:
            raise ValueError(f"LangGraph binding has no model for agent {name!r}")
        graph = create_agent(
            model=model,
            tools=tools,
            system_prompt=source.instructions,
            name=source.name,
        )
        native_agents[name] = graph
        observations.append(
            RuntimeObservation(
                "native-agent-constructed",
                name,
                {
                    "native_type": f"{type(graph).__module__}.{type(graph).__name__}",
                    "tool_names": [tool.name for tool in tools],
                },
            )
        )
        return graph

    build_agent(package.entry_name)
    for name in package.agents:
        build_agent(name)

    for agent in package.agents.values():
        assessments: dict[str, tuple[str, str]] = {
            "name": (
                "preserved",
                "LangChain create_agent assigns the source name to the native compiled graph.",
            ),
            "description": (
                (
                    "resolved",
                    "The description is the native StructuredTool description shown to a parent for routing.",
                )
                if agent.name in referenced
                else (
                    "resolved",
                    "A compiled LangGraph agent has no description property. The adapter retains the description in its agent catalog (artifact metadata) for discovery and diagnostics; it never enters the prompt.",
                )
            ),
            "instructions": (
                "preserved",
                "The Markdown body is supplied through create_agent(system_prompt=...) on every model turn.",
            ),
            "skills": (
                ("resolved", "The framework has no Agent Skills concept. The adapter supplies the dedicated tool activation pattern of the Agent Skills integration guide: catalog in the tool description, full body returned on demand as a tool result.")
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    (
                        "unsupported",
                        "Plugin MCP activation failed: " + "; ".join(activation_failures[agent.name]),
                    )
                    if activation_failures.get(agent.name)
                    else (
                        "resolved",
                        "Each plugin MCP server was connected through langchain-mcp-adapters and its tools attached to this agent's graph; the plugin wrapper is not retained.",
                    )
                    if activate
                    else (
                        "unsupported",
                        "The remote research MCP server was not activated during deterministic construction; no plugin tool is silently substituted.",
                    )
                )
                if agent.plugins
                else ("preserved", "The source agent declares no plugins.")
            ),
            "delegates": (
                (
                    "resolved",
                    "LangGraph has no agent relationship primitive. The adapter-authored StructuredTool implements the draft 0.1 contract: fresh child run, task in, text out, control returns to the parent.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(_capability_assessments(agent, binding))
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
            "skill_catalogs": skill_catalogs,
            "agent_catalog": {
                agent.name: {"name": agent.name, "description": agent.description}
                for agent in package.agents.values()
            },
            "mcp_tool_servers": tool_servers,
        },
    )


def _message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def run(artifact: RuntimeArtifact, task: str, *, activate_plugins: bool = False) -> RuntimeRun:
    from langchain_core.messages import AIMessage, ToolMessage

    entry_name = str(artifact.metadata["entry_name"])
    graph = artifact.native_agents[entry_name]
    tool_servers: dict[str, str] = dict(artifact.metadata.get("mcp_tool_servers", {}))
    start = len(artifact.observations)
    payload = {"messages": [{"role": "user", "content": task}]}
    if activate_plugins:
        # MCP tools from langchain-mcp-adapters are coroutine-only; use the async graph path.
        result = asyncio.run(graph.ainvoke(payload))
    else:
        result = graph.invoke(payload)
    observations: list[RuntimeObservation] = [
        item for item in artifact.observations[:start] if item.kind == "mcp-tools-discovered"
    ] if activate_plugins else []
    calls: dict[str, str] = {}
    for message in result["messages"]:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call["name"] in tool_servers:
                    calls[call["id"]] = call["name"]
                    observations.append(
                        RuntimeObservation(
                            "mcp-tool-invoked",
                            entry_name,
                            {"server": tool_servers[call["name"]], "tool": call["name"], "arguments": dict(call["args"])},
                        )
                    )
        if isinstance(message, ToolMessage) and message.tool_call_id in calls:
            name = calls[message.tool_call_id]
            observations.append(
                RuntimeObservation(
                    "mcp-tool-result",
                    entry_name,
                    {"server": tool_servers[name], "tool": name, "result": _message_text(message)},
                )
            )
    output = _message_text(result["messages"][-1])
    artifact.observations.append(RuntimeObservation("runtime-output", entry_name, {"result": output}))
    return RuntimeRun(output=output, observations=tuple(observations) + tuple(artifact.observations[start:]))
