from pathlib import Path

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.graph.state import CompiledStateGraph

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import langgraph as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"


class RecordingToolModel(FakeMessagesListChatModel):
    calls: list[list] = []

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def bindings() -> dict:
    return {
        "capabilities": {
            "reasoning": True,
            "tool-use": True,
            "vision-input": False,
        },
        "models": {
            "lead-researcher": RecordingToolModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "explorer",
                                "args": {"task": "Find primary evidence."},
                                "id": "delegate-1",
                                "type": "tool_call",
                            }
                        ],
                    ),
                    AIMessage(content="Final synthesis from evidence."),
                ]
            ),
            "explorer": RecordingToolModel(
                responses=[AIMessage(content="Primary evidence with limits.")]
            ),
            "critic": RecordingToolModel(
                responses=[AIMessage(content="The strongest objection.")]
            ),
        },
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(
        finding.status
        for finding in artifact.report.findings
        if finding.agent == agent and finding.feature == feature
    )


def test_builds_real_langgraph_agents_and_reports_semantics_independently() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    artifact = adapter.build(package, bindings(), strict=False)

    assert set(artifact.native_agents) == {"lead-researcher", "explorer", "critic"}
    assert all(isinstance(agent, CompiledStateGraph) for agent in artifact.native_agents.values())
    assert artifact.native_agents["lead-researcher"].name == "lead-researcher"
    assert status(artifact, "lead-researcher", "name") == "preserved"
    assert status(artifact, "lead-researcher", "description") == "resolved"
    assert artifact.metadata["agent_catalog"]["lead-researcher"]["description"] == package.entry.description
    assert status(artifact, "explorer", "description") == "resolved"
    assert status(artifact, "lead-researcher", "skills") == "resolved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "plugins") == "unsupported"
    assert status(artifact, "lead-researcher", "delegates") == "resolved"
    assert status(artifact, "lead-researcher", "model.prefers.vision-input") == "omitted-preference"


def test_native_langgraph_runtime_returns_control_after_specialist_tool_call() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    binding = bindings()
    artifact = adapter.build(package, binding, strict=False)

    result = adapter.run(artifact, "Investigate the claim.")

    assert result.output == "Final synthesis from evidence."
    events = [(item.kind, item.agent, dict(item.data)) for item in result.observations]
    assert events == [
        (
            "delegate-started",
            "lead-researcher",
            {"delegate": "explorer", "mechanism": "agent-as-tool", "task": "Find primary evidence."},
        ),
        (
            "delegate-returned",
            "lead-researcher",
            {"delegate": "explorer", "result": "Primary evidence with limits."},
        ),
        (
            "runtime-output",
            "lead-researcher",
            {"result": "Final synthesis from evidence."},
        ),
    ]
    lead_calls = binding["models"]["lead-researcher"].calls
    explorer_calls = binding["models"]["explorer"].calls
    assert any(
        message.type == "system" and package.entry.instructions in message.content
        for message in lead_calls[0]
    )
    assert any(
        message.type == "system"
        and package.agents["explorer"].instructions in message.content
        for message in explorer_calls[0]
    )


def test_strict_langgraph_rejects_only_the_unactivated_plugin() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    with pytest.raises(RuntimeCompatibilityError, match="plugins"):
        adapter.build(package, bindings(), strict=True)
