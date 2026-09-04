from __future__ import annotations

import json
from typing import Any, Mapping

from .model import Agent, CompatibilityReport, VALID_COMPATIBILITY_STATUSES


VALID_STATUSES = set(VALID_COMPATIBILITY_STATUSES)


def add_identity_and_instructions(report: CompatibilityReport, agent: Agent) -> None:
    report.add(agent.name, "identity", "preserved", "Name and discovery description are emitted natively.")
    report.add(agent.name, "instructions", "preserved", "Markdown instructions are emitted as the native persistent prompt.")


def resolve_model_requirements(
    report: CompatibilityReport,
    agent: Agent,
    binding: Mapping[str, Any],
    *,
    resolution_detail: str,
) -> None:
    capabilities = binding.get("capabilities", {})
    if not isinstance(capabilities, Mapping):
        capabilities = {}
    for capability in sorted(agent.requires):
        status = "resolved" if capabilities.get(capability) is True else "unsupported"
        detail = (
            resolution_detail
            if status == "resolved"
            else f"Target binding does not attest required capability {capability!r}."
        )
        report.add(agent.name, f"model.requires.{capability}", status, detail)
    for capability in sorted(agent.prefers):
        status = "resolved" if capabilities.get(capability) is True else "omitted-preference"
        detail = (
            resolution_detail
            if status == "resolved"
            else f"Target binding does not attest preferred capability {capability!r}."
        )
        report.add(agent.name, f"model.prefers.{capability}", status, detail)


def report_json(report: CompatibilityReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=False, ensure_ascii=False) + "\n"
