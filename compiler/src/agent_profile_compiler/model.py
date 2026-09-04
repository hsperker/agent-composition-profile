from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


VALID_COMPATIBILITY_STATUSES = frozenset(
    {
        "preserved",
        "resolved",
        "approximated",
        "unsupported",
        "omitted-preference",
        "unverified",
    }
)

# Statuses that assert a known semantic loss. `unverified` is deliberately not
# among them: it records a property that was not exercised, not a mismatch.
BLOCKING_STATUSES = frozenset({"approximated", "unsupported"})

# Conformance modules. Core is name plus instructions; every other module is an
# optional capability module a host may or may not implement.
MODULES = ("core", "description", "model", "skills", "plugins", "delegates")


def module_of(feature: str) -> str:
    """Map one source semantic feature to its conformance module."""

    if feature in {"name", "instructions"}:
        return "core"
    if feature == "description":
        return "description"
    if feature.startswith("model."):
        return "model"
    if feature == "skills" or feature.startswith("skills."):
        return "skills"
    if feature == "plugins" or feature.startswith("plugins."):
        return "plugins"
    if feature == "delegates":
        return "delegates"
    raise ValueError(f"unknown source semantic feature {feature!r}")


class ProfileError(ValueError):
    """Raised when a source declaration or package violates the profile."""


@dataclass(frozen=True)
class Skill:
    root: Path
    name: str
    description: str
    instructions: str


@dataclass(frozen=True)
class McpServer:
    name: str
    config: Mapping[str, Any]
    # Root of the Agent Plugin that declared the server. Agent Plugins §9 expands
    # ${PLUGIN_ROOT} against it and requires it in the server environment.
    plugin_root: Path | None = None


@dataclass(frozen=True)
class Plugin:
    root: Path
    name: str
    skills: tuple[Skill, ...] = ()
    mcp_servers: tuple[McpServer, ...] = ()


@dataclass(frozen=True)
class Agent:
    source_path: Path
    relative_path: Path
    name: str
    description: str
    instructions: str
    requires: frozenset[str] = frozenset()
    prefers: frozenset[str] = frozenset()
    direct_skills: tuple[Skill, ...] = ()
    plugins: tuple[Plugin, ...] = ()
    delegate_paths: tuple[Path, ...] = ()
    delegate_names: tuple[str, ...] = ()

    @property
    def all_skills(self) -> tuple[Skill, ...]:
        return self.direct_skills + tuple(
            skill for plugin in self.plugins for skill in plugin.skills
        )

    @property
    def mcp_servers(self) -> tuple[McpServer, ...]:
        return tuple(
            server for plugin in self.plugins for server in plugin.mcp_servers
        )


@dataclass(frozen=True)
class Package:
    root: Path
    entry_name: str
    agents: Mapping[str, Agent]

    @property
    def entry(self) -> Agent:
        return self.agents[self.entry_name]


@dataclass(frozen=True)
class Finding:
    agent: str
    feature: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "agent": self.agent,
            "feature": self.feature,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class CompatibilityReport:
    target: str
    source_entry: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def has_unsupported(self) -> bool:
        return any(finding.status == "unsupported" for finding in self.findings)

    @property
    def has_blocking_loss(self) -> bool:
        return any(finding.status in BLOCKING_STATUSES for finding in self.findings)

    @property
    def has_unverified(self) -> bool:
        return any(finding.status == "unverified" for finding in self.findings)

    def module_outcomes(self) -> dict[str, dict[str, Any]]:
        """Strict outcome per conformance module, computed from the findings."""

        outcomes: dict[str, dict[str, Any]] = {}
        for module in MODULES:
            findings = [f for f in self.findings if module_of(f.feature) == module]
            blocking = [f"{f.agent}:{f.feature}" for f in findings if f.status in BLOCKING_STATUSES]
            unverified = [f"{f.agent}:{f.feature}" for f in findings if f.status == "unverified"]
            if not findings:
                outcome = "not-declared"
            elif blocking:
                outcome = "rejected"
            else:
                outcome = "accepted"
            outcomes[module] = {"outcome": outcome, "blocking": blocking, "unverified": unverified}
        return outcomes

    def add(self, agent: str, feature: str, status: str, detail: str) -> None:
        if status not in VALID_COMPATIBILITY_STATUSES:
            allowed = ", ".join(sorted(VALID_COMPATIBILITY_STATUSES))
            raise ValueError(
                f"invalid compatibility status {status!r}; expected one of {allowed}"
            )
        self.findings.append(Finding(agent, feature, status, detail))

    def to_dict(self) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.status] = counts.get(finding.status, 0) + 1
        return {
            "target": self.target,
            "source_entry": self.source_entry,
            "has_unsupported": self.has_unsupported,
            "has_blocking_loss": self.has_blocking_loss,
            "has_unverified": self.has_unverified,
            "summary": dict(sorted(counts.items())),
            "modules": self.module_outcomes(),
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class CompilationResult:
    files: Mapping[str, str]
    report: CompatibilityReport
