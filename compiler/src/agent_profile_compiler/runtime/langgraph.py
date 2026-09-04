"""LangChain/LangGraph runtime experiment."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..model import CompatibilityReport, Package
from .common import assess_agent_semantics, enforce_strict_runtime
from .model import RuntimeArtifact, RuntimeObservation, RuntimeRun
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
                        "Activate one skill from this agent-private catalog. Available metadata: "
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
                    "unsupported",
                    "A standalone LangChain compiled agent has no native discovery-description property.",
                )
            ),
            "instructions": (
                "preserved",
                "The Markdown body is supplied through create_agent(system_prompt=...) on every model turn.",
            ),
            "skills": (
                (
                    "approximated",
                    "A native tool progressively returns skill text, but its result has tool-output authority rather than instruction authority.",
                )
                if agent.all_skills
                else ("preserved", "The source agent declares no skills.")
            ),
            "plugins": (
                (
                    "unsupported",
                    "The remote research MCP server was not activated during deterministic construction; no plugin tool is silently substituted.",
                )
                if agent.plugins
                else ("preserved", "The source agent declares no plugins.")
            ),
            "delegates": (
                (
                    "preserved",
                    "Each declared specialist is a native StructuredTool that starts a fresh child graph invocation and returns text to the parent.",
                )
                if agent.delegate_names
                else ("preserved", "The source agent declares no delegates.")
            ),
        }
        assessments.update(_capability_assessments(agent, binding))
        assess_agent_semantics(report, agent, assessments)

    if strict:
        enforce_strict_runtime(report)
    return RuntimeArtifact(
        target=TARGET,
        native_agents=native_agents,
        report=report,
        observations=observations,
        metadata={"entry_name": package.entry_name, "skill_catalogs": skill_catalogs},
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


def run(artifact: RuntimeArtifact, task: str) -> RuntimeRun:
    entry_name = str(artifact.metadata["entry_name"])
    start = len(artifact.observations)
    result = artifact.native_agents[entry_name].invoke(
        {"messages": [{"role": "user", "content": task}]}
    )
    output = _message_text(result["messages"][-1])
    artifact.observations.append(
        RuntimeObservation("runtime-output", entry_name, {"result": output})
    )
    return RuntimeRun(output=output, observations=tuple(artifact.observations[start:]))
