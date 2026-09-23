from __future__ import annotations

from typing import Any, Mapping

from ..model import CompilationResult, CompatibilityReport, Package
from ..report import add_identity_and_instructions, report_json, resolve_model_requirements
from .common import (
    copy_tree_to_files,
    global_skill_catalog,
    lowered_server,
    map_agent_plugin_mcp_to_claude,
    markdown_with_frontmatter,
)


def compile_target(package: Package, binding: Mapping[str, Any]) -> CompilationResult:
    report = CompatibilityReport(target="claude-code", source_entry=package.entry_name)
    files: dict[str, str] = {}
    model = binding.get("model")
    entry_mode = binding.get("entry_mode", "subagent")

    global_skills, conflicting_skill_names = global_skill_catalog(package)
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
        frontmatter: dict[str, Any] = {"name": agent.name}
        if agent.description is not None:
            frontmatter["description"] = agent.description
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
                map_agent_plugin_mcp_to_claude(lowered_server(server, binding)) for server in agent.mcp_servers
            ]
            tools.extend(f"mcp__{server.name}__*" for server in agent.mcp_servers)
            plugin_conflicts = sorted(
                {skill.name for plugin in agent.plugins for skill in plugin.skills}
                & conflicting_skill_names
            )
            # Claude Code's MCP configuration has no cwd field; the probe confirmed a stdio
            # server runs in the project directory. Agent Plugins §7.2.1 requires the
            # declared cwd or the plugin root, so any stdio server is a loss.
            stdio_servers = [server.name for server in agent.mcp_servers if server.config.get("type") == "stdio"]
            if stdio_servers:
                report.add(
                    agent.name,
                    "plugins",
                    "unsupported",
                    "Claude Code MCP configuration has no cwd field, so the Agent Plugins working directory cannot be "
                    "honored for stdio servers: " + ", ".join(stdio_servers),
                )
            elif plugin_conflicts:
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
                    "Agent Plugin skills are copied as project skills and MCP servers are lowered to the agent's mcpServers; Claude Code loads them once the project is trusted.",
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

        if agent.subagent_names:
            if agent.name == package.entry_name and entry_mode == "main":
                tools.append(f"Agent({', '.join(agent.subagent_names)})")
                report.add(
                    agent.name,
                    "subagents",
                    "preserved",
                    "When launched as the main agent, Claude Code enforces the subagent allowlist with Agent(name, ...); each call is a bounded task whose final report returns to the caller.",
                )
            else:
                tools.append("Agent")
                report.add(
                    agent.name,
                    "subagents",
                    "resolved",
                    "Claude Code permits nested subagent calls, so the listed agents are available as bounded tasks, but it ignores the Agent(type) list inside subagent definitions; availability holds, the allowlist is not enforced.",
                )
        else:
            # Explicitly omit Agent, preventing this generated subagent from spawning subagents.
            report.add(agent.name, "subagents", "preserved", "No Agent tool is emitted for a leaf agent.")

        if tools:
            frontmatter["tools"] = tools
        files[f".claude/agents/{agent.name}.md"] = markdown_with_frontmatter(
            frontmatter, agent.instructions
        )

    files["compatibility-report.json"] = report_json(report)
    return CompilationResult(files=files, report=report)
