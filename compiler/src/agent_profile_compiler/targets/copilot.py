"""GitHub Copilot custom agents: `.github/agents/<name>.agent.md`.

Read by VS Code and by the Copilot coding agent. Skills go to `.github/skills`.
MCP has two surfaces with different reach: `mcp-servers` in the agent file is
read only by the cloud coding agent, `.vscode/mcp.json` only by VS Code and it
is workspace wide. Both are emitted.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..model import CompilationResult, CompatibilityReport, McpServer, Package
from ..report import add_identity_and_instructions, report_json, resolve_model_requirements
from .common import copy_tree_to_files, global_skill_catalog, lowered_server, markdown_with_frontmatter


def map_mcp_for_cloud_agent(server: McpServer) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Agent Plugins MCP entry to the coding agent's `mcpServers` shape."""

    config = dict(server.config)
    transport = config.pop("type")
    losses: list[str] = []
    if transport == "stdio":
        mapped: dict[str, Any] = {"type": "local", "command": config["command"], "args": list(config.get("args", []))}
        if config.get("env"):
            mapped["env"] = dict(config["env"])
        # Agent Plugins requires a working directory (declared or the plugin root default);
        # the coding agent configuration has no such field.
        losses.append(f"{server.name}: Copilot coding agent MCP configuration has no cwd, so the Agent Plugins working directory cannot be honored")
    else:
        mapped = {"type": "http" if transport == "streamable-http" else "sse", "url": config["url"]}
        if config.get("headers"):
            mapped["headers"] = dict(config["headers"])
    mapped["tools"] = ["*"]
    return mapped, tuple(losses)


def map_mcp_for_vscode(server: McpServer) -> dict[str, Any]:
    """Agent Plugins MCP entry to `.vscode/mcp.json` `servers`."""

    config = dict(server.config)
    transport = config.pop("type")
    if transport == "stdio":
        mapped: dict[str, Any] = {"type": "stdio", "command": config["command"], "args": list(config.get("args", []))}
        for key in ("env", "cwd"):
            if config.get(key):
                mapped[key] = config[key]
        return mapped
    mapped = {"type": "http" if transport == "streamable-http" else "sse", "url": config["url"]}
    if config.get("headers"):
        mapped["headers"] = dict(config["headers"])
    return mapped


def compile_target(package: Package, binding: Mapping[str, Any]) -> CompilationResult:
    report = CompatibilityReport(target="copilot", source_entry=package.entry_name)
    files: dict[str, str] = {}
    model = binding.get("model")

    catalog, conflicts = global_skill_catalog(package)
    for skill in catalog.values():
        copy_tree_to_files(skill.root, f".github/skills/{skill.name}", files)

    workspace_servers: dict[str, Any] = {}
    for agent in package.agents.values():
        add_identity_and_instructions(report, agent)
        resolve_model_requirements(
            report, agent, binding,
            resolution_detail="External binding attests the capability and may select the Copilot model.",
        )
        frontmatter: dict[str, Any] = {"name": agent.name, "description": agent.description}
        if isinstance(model, str) and model:
            frontmatter["model"] = model

        agent_conflicts = sorted({skill.name for skill in agent.all_skills} & conflicts)
        if agent_conflicts:
            report.add(agent.name, "skills", "unsupported",
                       "Copilot discovers skills in one project-wide catalog, but the package contains different "
                       "skill directories with the same name: " + ", ".join(agent_conflicts))
        elif agent.all_skills:
            report.add(agent.name, "skills", "resolved",
                       "Agent Skills are copied to .github/skills, where Copilot discovers them project-wide and "
                       "activates them on demand; the catalog is not private to this agent.")
        else:
            report.add(agent.name, "skills", "preserved", "The agent declares no skills.")

        if agent.plugins:
            plugin_conflicts = sorted({skill.name for plugin in agent.plugins for skill in plugin.skills} & conflicts)
            losses: list[str] = list(f"plugin skill name collides in the project-wide catalog: {name}" for name in plugin_conflicts)
            cloud: dict[str, Any] = {}
            for server in map(lambda item: lowered_server(item, binding), agent.mcp_servers):
                mapped, server_losses = map_mcp_for_cloud_agent(server)
                cloud[server.name] = mapped
                losses.extend(server_losses)
                workspace_servers[server.name] = map_mcp_for_vscode(server)
            if cloud:
                frontmatter["mcp-servers"] = cloud
            if losses:
                report.add(agent.name, "plugins", "unsupported", "Copilot MCP configuration losses: " + "; ".join(losses))
            else:
                report.add(agent.name, "plugins", "resolved",
                           "Plugin skills are copied to .github/skills. MCP servers are emitted twice: in the agent file "
                           "for the cloud coding agent, where they are per agent, and in .vscode/mcp.json for VS Code, "
                           "where they are workspace wide.")
        else:
            report.add(agent.name, "plugins", "preserved", "The agent declares no plugins.")

        # Copilot enforces `agents` as the subagent allowlist for the `agent` tool. An empty
        # list keeps a leaf agent from spawning anything, mirroring the Claude Code target.
        frontmatter["agents"] = list(agent.subagent_names)
        if agent.subagent_names:
            report.add(agent.name, "subagents", "resolved",
                       "The agents list names the subagents; each runs as a bounded task through the task tool and "
                       "returns its result to the caller. Copilot CLI advertises and runs every custom agent in the "
                       "project regardless of the list (probe evidence), so the list is not an enforced allowlist there.")
        else:
            report.add(agent.name, "subagents", "preserved", "An empty agents list is emitted for a leaf agent.")

        files[f".github/agents/{agent.name}.agent.md"] = markdown_with_frontmatter(frontmatter, agent.instructions)

    if workspace_servers:
        files[".vscode/mcp.json"] = json.dumps({"servers": workspace_servers}, indent=2, ensure_ascii=False) + "\n"
    files["compatibility-report.json"] = report_json(report)
    return CompilationResult(files=files, report=report)
