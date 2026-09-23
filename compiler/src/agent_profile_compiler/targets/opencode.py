"""OpenCode agents: `.opencode/agent/<name>.md` plus `opencode.json`.

OpenCode 2.0.14 reads the singular `agent` directory; the documentation shows
`agents`, and a run with only that directory reports the agent as not found.

The filename is the agent identifier; there is no name field. Skills go to
`.opencode/skills` and are discovered project-wide through the skill tool.
MCP servers are configured once in `opencode.json` and are available to every
agent; `permission.task` is the per-agent subagent allowlist.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..model import CompilationResult, CompatibilityReport, McpServer, Package
from ..report import report_json, resolve_model_requirements
from .common import copy_tree_to_files, global_skill_catalog, lowered_server, markdown_with_frontmatter


def map_mcp_for_opencode(server: McpServer) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Agent Plugins MCP entry to the `mcp` section of opencode.json."""

    config = dict(server.config)
    transport = config.pop("type")
    if transport == "stdio":
        mapped: dict[str, Any] = {"type": "local", "command": [config["command"], *config.get("args", [])]}
        if config.get("env"):
            mapped["environment"] = dict(config["env"])
        if config.get("cwd"):
            mapped["cwd"] = config["cwd"]
        mapped["enabled"] = True
        return mapped, ()
    if transport == "streamable-http":
        mapped = {"type": "remote", "url": config["url"]}
        if config.get("headers"):
            mapped["headers"] = dict(config["headers"])
        mapped["enabled"] = True
        return mapped, ()
    return None, (f"{server.name}: OpenCode remote MCP servers use streamable HTTP; the Agent Plugins sse transport has no equivalent",)


def compile_target(package: Package, binding: Mapping[str, Any]) -> CompilationResult:
    report = CompatibilityReport(target="opencode", source_entry=package.entry_name)
    files: dict[str, str] = {}
    model = binding.get("model")
    entry_mode = binding.get("entry_mode", "primary")

    catalog, conflicts = global_skill_catalog(package)
    for skill in catalog.values():
        copy_tree_to_files(skill.root, f".opencode/skills/{skill.name}", files)

    mcp: dict[str, Any] = {}
    for agent in package.agents.values():
        report.add(agent.name, "name", "resolved",
                   "OpenCode derives the agent identifier from the filename; the file is named after the logical name and there is no name field.")
        report.add(agent.name, "description", "preserved", "The description is emitted as native frontmatter used for selection.")
        report.add(agent.name, "instructions", "preserved", "The Markdown body is the agent's system prompt.")
        resolve_model_requirements(
            report, agent, binding,
            resolution_detail="External binding attests the capability and may select the OpenCode provider/model.",
        )
        frontmatter: dict[str, Any] = {"mode": entry_mode if agent.name == package.entry_name else "subagent"}
        if agent.description is not None:
            frontmatter["description"] = agent.description
        if isinstance(model, str) and model:
            frontmatter["model"] = model

        agent_conflicts = sorted({skill.name for skill in agent.all_skills} & conflicts)
        if agent_conflicts:
            report.add(agent.name, "skills", "unsupported",
                       "OpenCode discovers skills in one project-wide catalog, but the package contains different "
                       "skill directories with the same name: " + ", ".join(agent_conflicts))
        elif agent.all_skills:
            report.add(agent.name, "skills", "resolved",
                       "Agent Skills are copied to .opencode/skills, where OpenCode discovers them project-wide and the "
                       "skill tool loads them on demand; the catalog is not private to this agent.")
        else:
            report.add(agent.name, "skills", "preserved", "The agent declares no skills.")

        if agent.plugins:
            losses: list[str] = list(f"plugin skill name collides in the project-wide catalog: {name}"
                                     for name in sorted({skill.name for plugin in agent.plugins for skill in plugin.skills} & conflicts))
            for server in map(lambda item: lowered_server(item, binding), agent.mcp_servers):
                mapped, server_losses = map_mcp_for_opencode(server)
                losses.extend(server_losses)
                if mapped is not None:
                    mcp[server.name] = mapped
            if losses:
                report.add(agent.name, "plugins", "unsupported", "OpenCode MCP configuration losses: " + "; ".join(losses))
            else:
                report.add(agent.name, "plugins", "resolved",
                           "Plugin skills are copied to .opencode/skills. MCP servers are configured in opencode.json, "
                           "where they are available to every agent in the project, not only the declaring one.")
        else:
            report.add(agent.name, "plugins", "preserved", "The agent declares no plugins.")

        task: dict[str, str] = {"*": "deny"}
        for child in agent.subagent_names:
            task[child] = "allow"
        frontmatter["permission"] = {"task": task}
        if agent.subagent_names:
            report.add(agent.name, "subagents", "preserved",
                       "permission.task is OpenCode's per-agent subagent allowlist; each listed agent runs as a bounded "
                       "task through the Task tool and returns its result to the caller.")
        else:
            report.add(agent.name, "subagents", "preserved", "Task permission is denied for a leaf agent.")

        files[f".opencode/agent/{agent.name}.md"] = markdown_with_frontmatter(frontmatter, agent.instructions)

    config: dict[str, Any] = {"$schema": "https://opencode.ai/config.json"}
    if mcp:
        config["mcp"] = mcp
    files["opencode.json"] = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    files["compatibility-report.json"] = report_json(report)
    return CompilationResult(files=files, report=report)
