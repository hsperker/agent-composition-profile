from __future__ import annotations

from typing import Any, Mapping

from ..model import CompilationResult, CompatibilityReport, Package
from ..report import add_identity_and_instructions, report_json, resolve_model_requirements
from .common import copy_tree_to_files, map_agent_plugin_mcp_to_claude, markdown_with_frontmatter


def _global_skills(package: Package):
    by_name = {}
    conflicts: set[str] = set()
    for agent in package.agents.values():
        for skill in agent.all_skills:
            prior = by_name.get(skill.name)
            if prior is not None and prior.root != skill.root:
                conflicts.add(skill.name)
                continue
            by_name[skill.name] = skill
    return {name: skill for name, skill in by_name.items() if name not in conflicts}, conflicts


def compile_target(package: Package, binding: Mapping[str, Any]) -> CompilationResult:
    report = CompatibilityReport(target="claude-code", source_entry=package.entry_name)
    files: dict[str, str] = {}
    model = binding.get("model")
    entry_mode = binding.get("entry_mode", "subagent")

    global_skills, conflicting_skill_names = _global_skills(package)
    for skill in global_skills.values():
        copy_tree_to_files(skill.root, f".claude/skills/{skill.name}", files)

    for agent in package.agents.values():
        add_identity_and_instructions(report, agent)
        resolve_model_requirements(
            report,
            agent,
            binding,
            resolution_detail="External binding attests the capability and selects the Claude Code model alias.",
        )
        frontmatter: dict[str, Any] = {
            "name": agent.name,
            "description": agent.description,
        }
        if isinstance(model, str) and model:
            frontmatter["model"] = model

        tools: list[str] = []
        agent_conflicts = sorted(
            {skill.name for skill in agent.all_skills} & conflicting_skill_names
        )
        usable_skills = [
            skill for skill in agent.all_skills if skill.name not in conflicting_skill_names
        ]
        if usable_skills:
            tools.append("Skill")
        if agent_conflicts:
            report.add(
                agent.name,
                "skills",
                "unsupported",
                "Claude Code discovers project skills in one global name space, but the package contains "
                "different skill directories with the same name: " + ", ".join(agent_conflicts),
            )
        elif agent.all_skills:
            report.add(
                agent.name,
                "skills",
                "resolved",
                "Agent Skills are copied to the project skill directory and activated on demand through "
                "Claude Code's Skill tool; the eager subagent skills field is not used.",
            )
        else:
            report.add(agent.name, "skills", "preserved", "The agent declares no skills.")

        if agent.mcp_servers:
            frontmatter["mcpServers"] = [
                map_agent_plugin_mcp_to_claude(server) for server in agent.mcp_servers
            ]
            tools.extend(f"mcp__{server.name}__*" for server in agent.mcp_servers)
            plugin_conflicts = sorted(
                {skill.name for plugin in agent.plugins for skill in plugin.skills}
                & conflicting_skill_names
            )
            if plugin_conflicts:
                report.add(
                    agent.name,
                    "plugins",
                    "unsupported",
                    "Plugin skill names collide in Claude Code's project-wide skill catalog: "
                    + ", ".join(plugin_conflicts),
                )
            else:
                report.add(
                    agent.name,
                    "plugins",
                    "resolved",
                    "Agent Plugin skills are copied as project skills and MCP servers are lowered to agent-scoped mcpServers.",
                )
        elif agent.plugins:
            plugin_conflicts = sorted(
                {skill.name for plugin in agent.plugins for skill in plugin.skills}
                & conflicting_skill_names
            )
            if plugin_conflicts:
                report.add(
                    agent.name,
                    "plugins",
                    "unsupported",
                    "Plugin skill names collide in Claude Code's project-wide skill catalog: "
                    + ", ".join(plugin_conflicts),
                )
            else:
                report.add(
                    agent.name,
                    "plugins",
                    "resolved",
                    "Agent Plugin skills are copied as project skills; the plugin declares no MCP servers.",
                )
        else:
            report.add(agent.name, "plugins", "preserved", "The agent declares no plugins.")

        if agent.delegate_names:
            if agent.name == package.entry_name and entry_mode == "main":
                tools.append(f"Agent({', '.join(agent.delegate_names)})")
                report.add(
                    agent.name,
                    "delegates",
                    "preserved",
                    "When launched as the main agent, Claude Code enforces the direct delegate allowlist with Agent(name, ...).",
                )
            else:
                tools.append("Agent")
                report.add(
                    agent.name,
                    "delegates",
                    "unsupported",
                    "Claude Code permits nested delegation, but ignores the type list in Agent(...) inside subagent definitions, so the direct catalog cannot be enforced natively.",
                )
        else:
            # Explicitly omit Agent, preventing this generated subagent from spawning delegates.
            report.add(agent.name, "delegates", "preserved", "No Agent tool is emitted for a leaf agent.")

        if tools:
            frontmatter["tools"] = tools
        files[f".claude/agents/{agent.name}.md"] = markdown_with_frontmatter(
            frontmatter, agent.instructions
        )

    files["compatibility-report.json"] = report_json(report)
    return CompilationResult(files=files, report=report)
