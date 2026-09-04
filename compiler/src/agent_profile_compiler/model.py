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
    }
)


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
        return any(
            finding.status in {"approximated", "unsupported"}
            for finding in self.findings
        )

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
            "summary": dict(sorted(counts.items())),
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class CompilationResult:
    files: Mapping[str, str]
    report: CompatibilityReport
