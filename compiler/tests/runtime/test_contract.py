import json
from pathlib import Path

import pytest

from agent_profile_compiler.model import Agent, CompatibilityReport, Skill, module_of
from agent_profile_compiler.runtime.common import (
    RuntimeCompatibilityError,
    assess_agent_semantics,
    capability_assessments,
    enforce_strict_runtime,
    skill_durability_assessment,
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


def skilled_agent() -> Agent:
    skill = Skill(root=Path("skills/demo"), name="demo", description="Demo.", instructions="Do it.")
    return Agent(
        source_path=Path("a.agent.md"),
        relative_path=Path("a.agent.md"),
        name="skilled",
        description="Uses a skill.",
        instructions="# Instructions",
        direct_skills=(skill,),
    )


def test_unverified_is_a_valid_status_that_strict_mode_does_not_block() -> None:
    report = CompatibilityReport(target="test-runtime", source_entry="skilled")
    report.add("skilled", "skills.durability", "unverified", "Not exercised.")

    enforce_strict_runtime(report)

    assert report.has_unverified
    assert not report.has_blocking_loss
    assert report.to_dict()["has_unverified"] is True


def test_agent_with_skills_requires_a_separate_durability_assessment() -> None:
    report = CompatibilityReport(target="test-runtime", source_entry="skilled")
    base = {
        "name": ("preserved", "n"),
        "description": ("preserved", "d"),
        "instructions": ("preserved", "i"),
        "skills": ("preserved", "s"),
        "plugins": ("preserved", "p"),
        "delegates": ("preserved", "g"),
    }

    with pytest.raises(ValueError, match="skills.durability"):
        assess_agent_semantics(report, skilled_agent(), base)

    assess_agent_semantics(report, skilled_agent(), {**base, **skill_durability_assessment(skilled_agent())})
    assert [f.status for f in report.findings if f.feature == "skills.durability"] == ["unverified"]
    assert skill_durability_assessment(agent()) == {}


def test_features_map_to_conformance_modules() -> None:
    assert module_of("name") == "core"
    assert module_of("instructions") == "core"
    assert module_of("description") == "description"
    assert module_of("model.requires.tool-use") == "model"
    assert module_of("model.prefers.vision-input") == "model"
    assert module_of("skills") == "skills"
    assert module_of("skills.durability") == "skills"
    assert module_of("plugins") == "plugins"
    assert module_of("delegates") == "delegates"
    with pytest.raises(ValueError):
        module_of("identity")


def test_module_outcomes_separate_core_from_optional_modules() -> None:
    report = CompatibilityReport(target="test-runtime", source_entry="lead-researcher")
    report.add("lead-researcher", "name", "preserved", "n")
    report.add("lead-researcher", "instructions", "preserved", "i")
    report.add("lead-researcher", "description", "approximated", "prompt content")
    report.add("lead-researcher", "skills", "resolved", "adapter tool")
    report.add("lead-researcher", "skills.durability", "unverified", "not exercised")
    report.add("lead-researcher", "model.prefers.vision-input", "omitted-preference", "none")

    modules = report.module_outcomes()

    assert modules["core"] == {"outcome": "accepted", "blocking": [], "unverified": []}
    assert modules["description"]["outcome"] == "rejected"
    assert modules["description"]["blocking"] == ["lead-researcher:description"]
    assert modules["skills"] == {
        "outcome": "accepted",
        "blocking": [],
        "unverified": ["lead-researcher:skills.durability"],
    }
    assert modules["model"]["outcome"] == "accepted"
    assert modules["plugins"]["outcome"] == "not-declared"
    assert modules["delegates"]["outcome"] == "not-declared"
    assert report.to_dict()["modules"] == modules
