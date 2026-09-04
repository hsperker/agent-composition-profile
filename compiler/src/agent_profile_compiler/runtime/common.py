from __future__ import annotations

from collections.abc import Mapping

from ..model import Agent, BLOCKING_STATUSES, CompatibilityReport, VALID_COMPATIBILITY_STATUSES


Assessment = tuple[str, str]


class RuntimeCompatibilityError(RuntimeError):
    """Raised when strict runtime construction would lose required meaning."""


def source_semantic_features(agent: Agent) -> tuple[str, ...]:
    return (
        "name",
        "description",
        "instructions",
        *(f"model.requires.{capability}" for capability in sorted(agent.requires)),
        *(f"model.prefers.{capability}" for capability in sorted(agent.prefers)),
        "skills",
        *(("skills.durability", "skills.resources") if agent.all_skills else ()),
        "plugins",
        "delegates",
    )


SKILL_DURABILITY_UNVERIFIED: Assessment = (
    "unverified",
    "Activated skill content enters context as a tool result. Whether it survives "
    "context compaction or summarization for the rest of the session was not exercised.",
)


SKILL_RESOURCES_UNVERIFIED: Assessment = (
    "unverified",
    "Agent Skills requires references, scripts, and assets to be reachable on demand. "
    "The fixture skills bundle no resources, so on-demand resource access was not exercised.",
)


def skill_durability_assessment(agent: Agent) -> dict[str, Assessment]:
    """The skills properties no runtime experiment exercised."""

    if not agent.all_skills:
        return {}
    return {
        "skills.durability": SKILL_DURABILITY_UNVERIFIED,
        "skills.resources": SKILL_RESOURCES_UNVERIFIED,
    }


def assess_agent_semantics(
    report: CompatibilityReport,
    agent: Agent,
    assessments: Mapping[str, Assessment],
) -> None:
    """Record exactly one explicit assessment for every source semantic."""

    expected = source_semantic_features(agent)
    missing = [feature for feature in expected if feature not in assessments]
    extra = sorted(set(assessments) - set(expected))
    if missing:
        raise ValueError("missing assessment for source semantic(s): " + ", ".join(missing))
    if extra:
        raise ValueError("assessment contains unknown source semantic(s): " + ", ".join(extra))

    for feature in expected:
        status, detail = assessments[feature]
        if status not in VALID_COMPATIBILITY_STATUSES:
            raise ValueError(f"invalid compatibility status {status!r} for {feature}")
        report.add(agent.name, feature, status, detail)


def capability_assessments(
    agent: Agent,
    binding: Mapping[str, object],
    *,
    resolved_detail: str,
) -> dict[str, Assessment]:
    capabilities = binding.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        capabilities = {}
    assessments: dict[str, Assessment] = {}
    for capability in sorted(agent.requires):
        assessments[f"model.requires.{capability}"] = (
            ("resolved", resolved_detail)
            if capabilities.get(capability) is True
            else (
                "unsupported",
                f"The target binding does not attest required capability {capability!r}.",
            )
        )
    for capability in sorted(agent.prefers):
        assessments[f"model.prefers.{capability}"] = (
            ("resolved", resolved_detail)
            if capabilities.get(capability) is True
            else (
                "omitted-preference",
                f"The target binding does not attest preferred capability {capability!r}.",
            )
        )
    return assessments


def enforce_strict_runtime(report: CompatibilityReport) -> None:
    blocking = [
        finding
        for finding in report.findings
        if not finding.feature.startswith("model.prefers.")
        and finding.status in BLOCKING_STATUSES
    ]
    if not blocking:
        return
    details = " | ".join(
        f"{finding.status} {finding.agent}:{finding.feature}: {finding.detail}"
        for finding in blocking
    )
    raise RuntimeCompatibilityError(
        f"strict runtime construction would lose required semantics for {report.target}: {details}"
    )
