from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..model import CompatibilityReport


@dataclass(frozen=True)
class RuntimeObservation:
    """One directly observed construction or runtime event."""

    kind: str
    agent: str
    data: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "agent": self.agent,
            "data": dict(sorted(self.data.items())),
        }


@dataclass
class RuntimeArtifact:
    """Native objects and the evidence recorded while constructing them."""

    target: str
    native_agents: Mapping[str, Any]
    report: CompatibilityReport
    observations: list[RuntimeObservation] = field(default_factory=list)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeRun:
    """Result of exercising one native framework runtime."""

    output: str
    observations: tuple[RuntimeObservation, ...] = ()
