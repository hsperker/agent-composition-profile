"""OpenCode product probe.

Compiles a package with the opencode target into a temporary project, adds a
custom OpenAI compatible provider that points at the scripted chat completions
server, runs `opencode run --standalone --agent <entry>` headless, and reports
what reached the model.

Isolation: HOME and the XDG directories point into the temporary directory, so
OpenCode neither reads the user's configuration and skills nor writes to their
data. PWD must be set explicitly because OpenCode resolves its project from
that variable rather than from the process working directory.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..compiler import compile_package
from ..model import Package
from .fake_openai import FakeOpenAI, reply_text, reply_tool_call, system_text, tool_names, tool_results

PRODUCT = "opencode"


def available() -> bool:
    return shutil.which("opencode") is not None


def version() -> str:
    try:
        return subprocess.run(["opencode", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


@dataclass
class ProbeResult:
    product: str
    version: str
    fixture: str
    exit_code: int
    final_output: str | None
    entry_instructions_in_system_prompt: bool
    tools_offered_to_entry: list[str]
    skill_catalog_advertised_before_activation: list[str]
    skill_body_absent_before_activation: bool
    skill_activated: str | None
    skill_body_in_context_after_activation: bool
    skill_body_persisted_in_later_turns: bool
    subagent_called: str | None
    subagent_ran_with_own_instructions: bool
    subagent_tools_offered: list[str]
    subagent_result_returned_to_caller: bool
    subagents_advertised: list[str]
    mcp_servers_connected: dict[str, str]
    mcp_tools_offered: list[str]
    mcp_results: list[dict[str, Any]]
    code_mode_search_result: str | None
    requests: int
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _write(files: dict[str, str], root: Path) -> None:
    for relative, content in files.items():
        if relative == "compatibility-report.json":
            continue
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _is_mcp_tool(name: str, builtin: set[str]) -> bool:
    return name not in builtin


BUILTIN_TOOLS = {"edit", "glob", "grep", "question", "read", "shell", "skill", "subagent", "task", "webfetch",
                 "websearch", "write", "execute", "bash", "list", "patch", "todowrite", "todoread", "lsp", "batch"}


def probe(package: Package, binding: dict[str, Any], *, task: str = "Investigate the claim.", timeout: int = 240) -> ProbeResult:
    entry = package.entry
    child_names = list(entry.subagent_names)
    skill_names = [skill.name for skill in entry.all_skills]
    child_marker = {name: package.agents[name].instructions.strip().splitlines()[-1] for name in child_names}
    entry_marker = entry.instructions.strip().splitlines()[-1]
    result = compile_package(package, PRODUCT, binding, strict=False)

    with tempfile.TemporaryDirectory(prefix="acp-opencode-probe-") as tmp:
        project = (Path(tmp) / "project").resolve()
        home = (Path(tmp) / "home").resolve()
        project.mkdir()
        for sub in ("config", "data", "cache", "state"):
            (home / sub).mkdir(parents=True)
        _write(result.files, project)
        log = Path(tmp) / "requests.jsonl"

        def director(request: dict[str, Any]) -> dict[str, Any]:
            system = system_text(request)
            names = tool_names(request)
            done = {item["tool"] for item in tool_results(request)}
            for child, marker in child_marker.items():
                if marker in system:
                    return reply_text(f"{child} result: bounded task done")
            if entry_marker not in system:
                return reply_text("unexpected caller")  # e.g. OpenCode's title generator
            if entry.plugins and not done:
                # OpenCode connects MCP servers asynchronously at startup; a real model would take
                # this long to answer, and the pause lets the stdio server finish its handshake.
                time.sleep(3)
            if skill_names and "skill" in names and "skill" not in done:
                return reply_tool_call("skill", {"id": skill_names[0]})
            mcp = [name for name in names if _is_mcp_tool(name, BUILTIN_TOOLS) and name not in done]
            if mcp:
                return reply_tool_call(mcp[0], {"text": "probe"})
            # OpenCode 2 reaches MCP tools through Code Mode. When no MCP tool is offered directly,
            # ask the Code Mode catalog once so the probe records what the model could have found.
            if entry.plugins and "execute" in names and "execute" not in done:
                return reply_tool_call("execute", {"code": 'const r = await search({query: "echo"}); return JSON.stringify(r);'})
            if child_names and "subagent" in names and "subagent" not in done:
                return reply_tool_call("subagent", {"agent": child_names[0], "description": "bounded task", "prompt": "Analyze this."})
            return reply_text("final answer from the entry agent")

        with FakeOpenAI(director, log) as fake:
            config = json.loads((project / "opencode.json").read_text(encoding="utf-8"))
            config.update({
                "provider": {"probe": {
                    "npm": "@ai-sdk/openai-compatible", "name": "Probe",
                    "options": {"baseURL": fake.base_url, "apiKey": "probe-key"},
                    "models": {"probe-model": {"name": "Probe model", "tool_call": True}},
                }},
                "model": "probe/probe-model",
                "autoupdate": False,
            })
            (project / "opencode.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
            env = dict(os.environ)
            env.update({
                "HOME": str(home),
                "XDG_CONFIG_HOME": str(home / "config"),
                "XDG_DATA_HOME": str(home / "data"),
                "XDG_CACHE_HOME": str(home / "cache"),
                "XDG_STATE_HOME": str(home / "state"),
                "PWD": str(project),
                "OPENCODE_DISABLE_AUTOUPDATE": "1",
                "OPENCODE_DISABLE_MODELS_FETCH": "1",
            })
            command = ["opencode", "run", "--standalone", "--auto", "--agent", entry.name, "--format", "json",
                       "--print-logs", "--log-level", "info", task]
            proc = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True,
                                  timeout=timeout, stdin=subprocess.DEVNULL)
            requests = [item["request"] for item in fake.requests()]

        events = []
        for line in proc.stdout.splitlines():
            if line.startswith("{"):
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        final_text = next((e["part"]["text"] for e in reversed(events) if e.get("type") == "text"), None)
        errors = [e["error"] for e in events if e.get("type") == "error"]

        entry_requests = [r for r in requests if entry_marker in system_text(r)]
        child_requests = {name: [r for r in requests if marker in system_text(r)] for name, marker in child_marker.items()}
        first = entry_requests[0] if entry_requests else {}
        first_blob = json.dumps(first)
        offered = tool_names(first)
        catalog = [name for name in skill_names if name in first_blob]
        all_results = [item for r in entry_requests for item in tool_results(r)]
        skill_activated = next((skill_names[0] for item in all_results if item["tool"] == "skill"), None) if skill_names else None
        skill_body = entry.all_skills[0].instructions.strip().splitlines()[-1] if entry.all_skills else None
        body_absent_before = bool(skill_body) and skill_body not in first_blob
        after_activation = [json.dumps(r) for r in entry_requests[1:]]
        body_after = bool(skill_body) and any(skill_body in blob for blob in after_activation[:1])
        body_persisted = bool(skill_body) and len(after_activation) > 1 and all(skill_body in blob for blob in after_activation)
        called_child = next((child_names[0] for item in all_results if item["tool"] == "subagent"), None) if child_names else None
        child_reqs = child_requests.get(called_child or "", [])
        child_tools = tool_names(child_reqs[0]) if child_reqs else []
        child_returned = called_child is not None and any(f"{called_child} result" in json.dumps(r) for r in entry_requests)
        subagent_tool = next((t.get("function", {}) for t in first.get("tools", []) if t.get("function", {}).get("name") == "subagent"), {})
        advertised = [name for name in package.agents if name != entry.name and f"- {name}:" in (subagent_tool.get("description") or "")]
        mcp_offered = sorted(name for name in offered if _is_mcp_tool(name, BUILTIN_TOOLS))
        mcp_results: list[dict[str, Any]] = []
        for item in all_results:
            if _is_mcp_tool(item["tool"], BUILTIN_TOOLS):
                entry_result = {"tool": item["tool"], "result": str(item["content"])[:400].replace(str(project), "${PROJECT_DIR}")}
                if entry_result not in mcp_results:
                    mcp_results.append(entry_result)
        notes = [f"opencode error: {error}" for error in errors]
        connected: dict[str, str] = {}
        for line in proc.stderr.splitlines():
            if 'message="mcp connected"' in line and "server=" in line:
                connected[line.split("server=")[1].split()[0]] = "connected"
            if 'message="mcp connect failed"' in line and "server=" in line:
                connected[line.split("server=")[1].split()[0]] = "failed"
        code_mode = next((str(item["content"])[:300] for item in all_results if item["tool"] == "execute"), None)
        if entry.plugins and not mcp_offered:
            notes.append("MCP servers connected but no MCP tool was offered to the model, directly or through the Code Mode catalog")
        return ProbeResult(
            product=PRODUCT, version=version(), fixture=str(package.root),
            exit_code=proc.returncode, final_output=final_text,
            entry_instructions_in_system_prompt=bool(entry_requests),
            tools_offered_to_entry=offered,
            skill_catalog_advertised_before_activation=catalog,
            skill_body_absent_before_activation=body_absent_before,
            skill_activated=skill_activated,
            skill_body_in_context_after_activation=body_after,
            skill_body_persisted_in_later_turns=body_persisted,
            subagent_called=called_child,
            subagent_ran_with_own_instructions=bool(child_reqs),
            subagent_tools_offered=child_tools,
            subagent_result_returned_to_caller=child_returned,
            subagents_advertised=advertised,
            mcp_servers_connected=connected,
            mcp_tools_offered=mcp_offered,
            mcp_results=mcp_results,
            code_mode_search_result=code_mode,
            requests=len(requests),
            notes=notes,
        )
