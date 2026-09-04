from __future__ import annotations

from typing import Any, Mapping

from ..model import CompilationResult, CompatibilityReport, Package
from ..report import add_identity_and_instructions, report_json, resolve_model_requirements
from .common import (
    copy_tree_to_files,
    map_agent_plugin_mcp_to_afm,
    markdown_with_frontmatter,
    strip_top_level_instructions_heading,
)


def compile_target(package: Package, binding: Mapping[str, Any]) -> CompilationResult:
    report = CompatibilityReport(target="afm", source_entry=package.entry_name)
    files: dict[str, str] = {}
    bound_model = binding.get("model")

    for agent in package.agents.values():
        add_identity_and_instructions(report, agent)
        resolve_model_requirements(
            report,
            agent,
            binding,
            resolution_detail="External deployment binding attests capabilities and supplies AFM's concrete model service fields.",
        )
        frontmatter: dict[str, Any] = {
            "spec_version": "0.4.0",
            "name": agent.name,
            "description": agent.description,
        }
        if isinstance(bound_model, Mapping) and bound_model:
            frontmatter["model"] = dict(bound_model)

        if agent.all_skills:
            skill_entries = []
            for skill in agent.all_skills:
                destination = f"skills/{skill.name}"
                copy_tree_to_files(skill.root, destination, files)
                skill_entries.append({"type": "local", "path": f"./{destination}"})
            frontmatter["skills"] = skill_entries
            report.add(
                agent.name,
                "skills",
                "preserved",
                "Agent Skills are copied and referenced through AFM local skill entries.",
            )
        else:
            report.add(agent.name, "skills", "preserved", "The agent declares no skills.")

        if agent.mcp_servers:
            mapped_servers = []
            mcp_losses: list[str] = []
            for server in agent.mcp_servers:
                mapped, losses = map_agent_plugin_mcp_to_afm(server)
                if mapped is not None:
                    mapped_servers.append(mapped)
                mcp_losses.extend(f"{server.name}: {loss}" for loss in losses)
            if mapped_servers:
                frontmatter["tools"] = {"mcp": mapped_servers}
            report.add(
                agent.name,
                "plugins",
                "unsupported" if mcp_losses else "resolved",
                (
                    "Cannot preserve all Agent Plugin MCP settings: " + "; ".join(mcp_losses)
                    if mcp_losses
                    else "Agent Plugin skills become AFM skills and MCP servers become AFM tools.mcp entries."
                ),
            )
        elif agent.plugins:
            report.add(
                agent.name,
                "plugins",
                "resolved",
                "Agent Plugin skills become AFM local skill entries; the plugin declares no MCP servers.",
            )
        else:
            report.add(agent.name, "plugins", "preserved", "The agent declares no plugins.")

        if agent.delegate_names:
            report.add(
                agent.name,
                "delegates",
                "unsupported",
                "AFM 0.4.0 does not define local delegate composition; its future-work section points to remote multi-agent interaction through A2A.",
            )
        else:
            report.add(agent.name, "delegates", "preserved", "The agent declares no delegates.")

        body = (
            f"# Role\n\n{agent.description.strip()}\n\n"
            f"# Instructions\n\n{strip_top_level_instructions_heading(agent.instructions)}"
        )
        files[f"{agent.name}.afm.md"] = markdown_with_frontmatter(frontmatter, body)

    files["compatibility-report.json"] = report_json(report)
    return CompilationResult(files=files, report=report)
