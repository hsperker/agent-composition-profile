from __future__ import annotations

from typing import Any, Mapping

from ..model import CompilationResult, CompatibilityReport, Package
from ..report import add_identity_and_instructions, report_json, resolve_model_requirements
from .common import markdown_with_frontmatter


def compile_target(package: Package, binding: Mapping[str, Any]) -> CompilationResult:
    report = CompatibilityReport(target="amplifier", source_entry=package.entry_name)
    files: dict[str, str] = {}
    model_roles = binding.get("model_roles", {})
    if not isinstance(model_roles, Mapping):
        model_roles = {}

    for agent in package.agents.values():
        add_identity_and_instructions(report, agent)
        resolve_model_requirements(
            report,
            agent,
            binding,
            resolution_detail="External binding attests the capability; Amplifier resolves the selected model role through its routing matrix.",
        )

        requested = sorted(agent.requires | agent.prefers)
        role: str | None = None
        # Prefer a role for required reasoning, then required/preferred vision.
        for capability in ("reasoning", "vision-input"):
            if capability in requested and isinstance(model_roles.get(capability), str):
                role = model_roles[capability]
                break

        meta: dict[str, Any] = {
            "name": agent.name,
            "description": agent.description,
        }
        if role:
            meta["model_role"] = role
        frontmatter: dict[str, Any] = {
            "meta": meta,
            "agents": list(agent.delegate_names) if agent.delegate_names else "none",
        }
        files[f"agents/{agent.name}.md"] = markdown_with_frontmatter(frontmatter, agent.instructions)

        report.add(
            agent.name,
            "delegates",
            "preserved",
            "Amplifier emits the direct delegate names through the agent allowlist.",
        )
        if agent.all_skills:
            report.add(
                agent.name,
                "skills",
                "unsupported",
                "The native agent file has no demonstrated Agent Skills reference with progressive-disclosure semantics; a runtime module shim is required.",
            )
        else:
            report.add(agent.name, "skills", "preserved", "The agent declares no skills.")
        if agent.plugins:
            report.add(
                agent.name,
                "plugins",
                "unsupported",
                "The native agent file cannot lower an Agent Plugin package without an Amplifier module or bundle adapter.",
            )
        else:
            report.add(agent.name, "plugins", "preserved", "The agent declares no plugins.")

    bundle_name = binding.get("bundle_name", "compiled-agent-profile")
    base_bundle = binding.get(
        "base_bundle",
        "git+https://github.com/microsoft/amplifier-foundation@main",
    )
    bundle_frontmatter = {
        "bundle": {
            "name": bundle_name,
            "version": "0.1.0",
            "description": "Generated from an Agent Composition Profile package",
        },
        "includes": [
            {"bundle": base_bundle},
            {"bundle": f"{bundle_name}:behaviors/agents"},
        ],
    }
    files["bundle.md"] = markdown_with_frontmatter(
        bundle_frontmatter,
        "# Compiled agent roster\n\n"
        "This bundle makes the compiled agents available for delegation. "
        f"The portable entry agent is `{package.entry_name}`.",
    )
    behavior = {
        "bundle": {
            "name": f"{bundle_name}-agents",
            "version": "0.1.0",
            "description": "Generated agent roster",
        },
        "agents": {"include": [f"{bundle_name}:{name}" for name in package.agents]},
    }
    files["behaviors/agents.yaml"] = __import__("yaml").safe_dump(
        behavior, sort_keys=False
    )
    files["compatibility-report.json"] = report_json(report)
    return CompilationResult(files=files, report=report)
