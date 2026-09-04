import json
from pathlib import Path

import pytest

from agent_profile_compiler.model import Agent, CompatibilityReport
from agent_profile_compiler.runtime.common import (
    RuntimeCompatibilityError,
    assess_agent_semantics,
    capability_assessments,
    enforce_strict_runtime,
)
from agent_profile_compiler.runtime.model import RuntimeObservation


def agent() -> Agent:
    return Agent(
        source_path=Path("lead.agent.md"),
        relative_path=Path("lead.agent.md"),
        name="lead-researcher",
        description="Researches and synthesizes evidence.",
        instructions="# Instructions\n\nUse the specialist.",
        requires=frozenset({"reasoning", "tool-use"}),
        prefers=frozenset({"vision-input"}),
        delegate_names=("explorer",),
    )


def test_assessment_records_each_source_semantic_separately() -> None:
    report = CompatibilityReport(target="test-runtime", source_entry="lead-researcher")

    assess_agent_semantics(
        report,
        agent(),
        {
            "name": ("preserved", "Native identity."),
            "description": ("approximated", "Used as prompt text."),
            "instructions": ("preserved", "Native system instructions."),
            "model.requires.reasoning": ("resolved", "Binding attests it."),
            "model.requires.tool-use": ("resolved", "Observed a tool call."),
            "model.prefers.vision-input": (
                "omitted-preference",
                "No bound vision model.",
            ),
            "skills": ("unsupported", "No progressive disclosure."),
            "plugins": ("resolved", "MCP tools are agent-scoped."),
            "delegates": ("approximated", "Control transfers."),
        },
    )

    assert [finding.feature for finding in report.findings] == [
        "name",
        "description",
        "instructions",
        "model.requires.reasoning",
        "model.requires.tool-use",
        "model.prefers.vision-input",
        "skills",
        "plugins",
        "delegates",
    ]


def test_assessment_rejects_a_silent_or_unknown_source_semantic() -> None:
    report = CompatibilityReport(target="test-runtime", source_entry="lead-researcher")

    with pytest.raises(ValueError, match="missing assessment.*plugins"):
        assess_agent_semantics(
            report,
            agent(),
            {
                "name": ("preserved", "Native identity."),
                "description": ("preserved", "Native metadata."),
                "instructions": ("preserved", "Native instructions."),
                "model.requires.reasoning": ("resolved", "Binding."),
                "model.requires.tool-use": ("resolved", "Binding."),
                "model.prefers.vision-input": (
                    "omitted-preference",
                    "Unavailable.",
                ),
                "skills": ("unsupported", "Unavailable."),
                "delegates": ("unsupported", "Unavailable."),
            },
        )


def test_strict_runtime_rejects_required_approximations_but_not_omitted_preferences() -> None:
    report = CompatibilityReport(target="test-runtime", source_entry="lead-researcher")
    report.add("lead-researcher", "model.prefers.vision-input", "omitted-preference", "Unavailable.")
    enforce_strict_runtime(report)

    report.add("lead-researcher", "delegates", "approximated", "Control transfers.")
    with pytest.raises(RuntimeCompatibilityError, match="delegates"):
        enforce_strict_runtime(report)


def test_missing_model_attestation_is_unsupported_not_assumed() -> None:
    assessments = capability_assessments(
        agent(),
        {"capabilities": {"tool-use": True}},
        resolved_detail="Binding attests it.",
    )

    assert assessments["model.requires.tool-use"][0] == "resolved"
    assert assessments["model.requires.reasoning"][0] == "unsupported"
    assert assessments["model.prefers.vision-input"][0] == "omitted-preference"


def test_compatibility_report_rejects_unknown_status() -> None:
    report = CompatibilityReport(target="test-runtime", source_entry="lead-researcher")

    with pytest.raises(ValueError, match="invalid compatibility status"):
        report.add("lead-researcher", "name", "looks-good", "Not canonical.")


def test_runtime_observation_json_is_stable_and_contains_framework_event_data() -> None:
    observation = RuntimeObservation(
        kind="delegate-returned",
        agent="lead-researcher",
        data={"result": "critique", "delegate": "critic"},
    )

    assert json.dumps(observation.to_dict(), sort_keys=True) == (
        '{"agent": "lead-researcher", "data": {"delegate": "critic", '
        '"result": "critique"}, "kind": "delegate-returned"}'
    )
