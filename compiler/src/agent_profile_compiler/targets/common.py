from __future__ import annotations

import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

import yaml

from ..model import McpServer, Skill


def markdown_with_frontmatter(frontmatter: Mapping[str, Any], body: str) -> str:
    dumped = yaml.safe_dump(
        dict(frontmatter),
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    ).rstrip()
    return f"---\n{dumped}\n---\n\n{body.rstrip()}\n"


def copy_tree_to_files(root: Path, destination: str, files: dict[str, str]) -> None:
    dest = PurePosixPath(destination)
    for source in sorted(root.rglob("*")):
        if source.is_file():
            rel = source.relative_to(root)
            try:
                content = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # The PoC output map is text-only. Preserve deterministic evidence for binary resources.
                content = source.read_bytes().hex()
            files[str(dest / PurePosixPath(rel.as_posix()))] = content


def map_agent_plugin_mcp_to_claude(server: McpServer) -> dict[str, Any]:
    config = dict(server.config)
    transport = config.pop("type")
    if transport == "streamable-http":
        transport = "http"
    mapped: dict[str, Any] = {"type": transport}
    for key in ("command", "args", "env", "cwd", "url", "headers"):
        if key in config:
            mapped[key] = config[key]
    return {server.name: mapped}


def map_agent_plugin_mcp_to_afm(server: McpServer) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    """Lower one Agent Plugins MCP server to AFM 0.4.0.

    AFM supports stdio and streamable HTTP, but not Agent Plugins' SSE transport,
    arbitrary HTTP headers, or stdio cwd. Diagnostic compilation may still emit
    the representable subset, while the caller reports the loss.
    """
    config = dict(server.config)
    transport_type = config.pop("type")
    losses: list[str] = []
    if transport_type == "streamable-http":
        transport_type = "http"
    elif transport_type == "sse":
        return None, ("Agent Plugins SSE transport has no AFM 0.4.0 equivalent",)

    transport: dict[str, Any] = {"type": transport_type}
    if transport_type == "stdio":
        for key in ("command", "args", "env"):
            if key in config:
                transport[key] = config[key]
        if "cwd" in config:
            losses.append("AFM 0.4.0 stdio transport has no cwd field")
    else:
        if "url" in config:
            transport["url"] = config["url"]
        if "headers" in config:
            losses.append("AFM 0.4.0 cannot express arbitrary Agent Plugins HTTP headers")
    return {"name": server.name, "transport": transport}, tuple(losses)


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def strip_top_level_instructions_heading(body: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.strip():
            if line.strip().lower() == "# instructions":
                lines = lines[:index] + lines[index + 1 :]
                while lines and not lines[0].strip():
                    lines.pop(0)
            break
    return "\n".join(lines).strip()
