"""Codex CLI product probe.

Compiles a package with the codex target into a temporary project, writes a
private CODEX_HOME with a custom model provider that points at the scripted
Responses API server, runs `codex exec --json` headless, and reports what
reached the model: instructions, skills, subagents, and plugin MCP tools.

Codex has no notion of running a custom agent as the main thread; custom
agents are spawned as subagents. The probe therefore runs the entry agent's
instructions as the thread's developer instructions (Codex reads AGENTS.md from
the project) and drives the subagent call through Codex's multi agent tools.
Where a Codex behavior is unknown the probe records the raw tool list and the
request shapes instead of guessing, so the first run on a new version is an
observation run.

Isolation: CODEX_HOME points into the temporary directory, so the user's
~/.codex configuration and login are untouched.
"""

from __future__ import annotations

import json
import os
import time
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..compiler import compile_package
from ..model import Package
from .fake_responses import FakeResponses, context_text, instructions_text, namespaced_tools, reply_function_call, reply_text, tool_names, tool_namespace, tool_results

PRODUCT = "codex"
SUBAGENT_TOOLS = ("spawn_agent", "send_input", "wait_agent", "close_agent", "resume_agent")


def available() -> bool:
    return shutil.which("codex") is not None


def version() -> str:
    try:
        return subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def evidence_dir() -> str:
    return PRODUCT


@dataclass
class ProbeResult:
    product: str
    version: str
    fixture: str
    exit_code: int
    final_output: str | None
    entry_instructions_in_instructions: bool
    entry_instructions_delivered_as: str | None
    tools_offered_to_entry: list[str]
    skill_catalog_advertised_before_activation: list[str]
    skill_body_absent_before_activation: bool
    skill_activated: str | None
    skill_body_in_context_after_activation: bool
    skill_body_persisted_in_later_turns: bool
    subagent_tools_offered: list[str]
    subagent_called: str | None
    subagent_ran_with_own_instructions: bool
    subagent_result_returned_to_caller: bool
    subagents_advertised: list[str]
    mcp_tools_offered: list[str]
    mcp_tools_by_request: list[list[str]]
    mcp_log: list[str]
    mcp_results: list[dict[str, Any]]
    requests: int
    request_shapes: list[dict[str, Any]]
    first_request_excerpt: dict[str, Any]
    stderr_tail: str
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


def probe(package: Package, binding: dict[str, Any], *, task: str = "Investigate the claim.", timeout: int = 300) -> ProbeResult:
    entry = package.entry
    child_names = list(entry.subagent_names)
    skill_names = [skill.name for skill in entry.all_skills]
    child_marker = {name: package.agents[name].instructions.strip().splitlines()[-1] for name in child_names}
    entry_marker = entry.instructions.strip().splitlines()[-1]
    result = compile_package(package, PRODUCT, binding, strict=False)

    # Codex refuses to create helper binaries under /tmp, so the probe works under ~/.cache.
    cache_root = Path.home() / ".cache" / "acp-probe"
    cache_root.mkdir(parents=True, exist_ok=True)
    # Codex keeps writing plugin caches under CODEX_HOME for a moment after exit; a directory that
    # is not yet empty must not fail the probe.
    with tempfile.TemporaryDirectory(prefix="codex-", dir=cache_root, ignore_cleanup_errors=True) as tmp:
        project = (Path(tmp) / "project").resolve()
        codex_home = (Path(tmp) / "codex-home").resolve()
        project.mkdir()
        codex_home.mkdir()
        _write(result.files, project)  # includes AGENTS.md: the binding's entry_mode is main
        log = Path(tmp) / "requests.jsonl"

        skill_body_marker = entry.all_skills[0].instructions.strip().splitlines()[-1] if entry.all_skills else None

        def director(request: dict[str, Any]) -> dict[str, Any]:
            context = context_text(request)  # instructions, developer messages, AGENTS.md message
            names = tool_names(request)
            results = tool_results(request)
            done = {item["tool"] for item in results}
            # Every thread in the project receives AGENTS.md, so a child is recognised by its own
            # developer instructions, not by the absence of the entry marker.
            for child, marker in child_marker.items():
                if marker in context:
                    return reply_text(f"{child} result: bounded task done")
            if skill_body_marker and "exec_command" in names and not any(skill_body_marker in str(r["content"]) for r in results):
                # Codex lists skills with their SKILL.md paths in a developer message; activation is a file read.
                return reply_function_call("exec_command", {"cmd": f"cat .agents/skills/{skill_names[0]}/SKILL.md"})
            if entry.plugins and not results:
                # Codex starts MCP servers in the background and a turn proceeds without servers that
                # are still initializing. A real model takes this long to answer; the pause lets a slow
                # stdio server (Python on a Raspberry Pi) finish its handshake before the next step.
                time.sleep(10)
            # MCP tools arrive inside one namespace tool per server, named mcp__<server>.
            mcp = [(name, ns) for name, ns in namespaced_tools(request).items() if ns.startswith("mcp__") and name not in done]
            if mcp:
                return reply_function_call(mcp[0][0], {"text": "probe"}, namespace=mcp[0][1])
            # Multi agent tools live in a namespace tool; Codex routes the call only when the
            # function_call item names that namespace. `agent_type` selects a custom agent.
            if child_names and "spawn_agent" in names and "spawn_agent" not in done:
                return reply_function_call("spawn_agent", {"agent_type": child_names[0], "message": "Analyze this."},
                                           namespace=tool_namespace(request, "spawn_agent"))
            if "wait_agent" in names and "spawn_agent" in done and "wait_agent" not in done:
                spawn_output = next((r["content"] for r in results if r["tool"] == "spawn_agent"), "")
                agent_id = _extract_agent_id(spawn_output)
                return reply_function_call("wait_agent", {"targets": [agent_id] if agent_id else [], "timeout_ms": 60000},
                                           namespace=tool_namespace(request, "wait_agent"))
            return reply_text("final answer from the entry agent")

        with FakeResponses(director, log) as fake:
            (codex_home / "config.toml").write_text(
                "\n".join([
                    'model = "probe-model"',
                    'model_provider = "probe"',
                    'approval_policy = "never"',
                    'sandbox_mode = "danger-full-access"',
                    "",
                    "[model_providers.probe]",
                    'name = "Probe"',
                    f'base_url = "{fake.base_url}"',
                    'env_key = "PROBE_API_KEY"',
                    'wire_api = "responses"',
                    "",
                    "[features]",
                    "multi_agent = true",
                    "",
                    # Project-level .codex/config.toml is honored only for trusted projects.
                    f'[projects."{project}"]',
                    'trust_level = "trusted"',
                    "",
                ]),
                encoding="utf-8",
            )
            env = dict(os.environ)
            env.update({"CODEX_HOME": str(codex_home), "PROBE_API_KEY": "probe-key", "PWD": str(project)})
            # MCP startup problems are logged, not fatal; keep those lines visible in the evidence.
            env.setdefault("RUST_LOG", "warn,rmcp::service=debug")
            command = ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check", "-C", str(project), task]
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
        final_text = None
        for event in reversed(events):
            blob = json.dumps(event)
            if "agent_message" in blob or "item.completed" in blob:
                final_text = blob[:400]
                break

        def _is_child(request: dict[str, Any]) -> bool:
            return any(marker in context_text(request) for marker in child_marker.values())

        entry_requests = [r for r in requests if entry_marker in context_text(r) and not _is_child(r)]
        child_requests = {name: [r for r in requests if marker in context_text(r)] for name, marker in child_marker.items()}
        first = entry_requests[0] if entry_requests else (requests[0] if requests else {})
        first_blob = json.dumps(first)
        offered = tool_names(first)
        catalog = [name for name in skill_names if name in first_blob]
        skill_body = entry.all_skills[0].instructions.strip().splitlines()[-1] if entry.all_skills else None
        body_absent_before = bool(skill_body) and skill_body not in first_blob
        all_results = [item for r in entry_requests for item in tool_results(r)]
        skill_activated = skill_names[0] if skill_body and any(skill_body in str(item["content"]) for item in all_results) else None
        after = [json.dumps(r) for r in entry_requests[1:]]
        body_after = bool(skill_body) and any(skill_body in blob for blob in after[:1])
        body_persisted = bool(skill_body) and len(after) > 1 and all(skill_body in blob for blob in after)
        called_child = child_names[0] if child_names and any(item["tool"] == "spawn_agent" for item in all_results) else None
        child_reqs = child_requests.get(called_child or "", [])
        child_returned = called_child is not None and any(f"{called_child} result" in json.dumps(r) for r in entry_requests)
        spawn_tool = _namespaced_function(first, "spawn_agent")
        advertised = [name for name in package.agents if name != entry.name and name in json.dumps(spawn_tool)]
        # Servers can join between steps, so the offer is recorded per entry request and as a union.
        mcp_by_request = [sorted(f"{ns}.{name}" for name, ns in namespaced_tools(r).items() if ns.startswith("mcp__")) for r in entry_requests]
        mcp_namespaces = {name: ns for r in entry_requests for name, ns in namespaced_tools(r).items() if ns.startswith("mcp__")}
        mcp_offered = sorted(f"{ns}.{name}" for name, ns in mcp_namespaces.items())
        mcp_results: list[dict[str, Any]] = []
        for item in all_results:
            if item["tool"] in mcp_namespaces:
                entry_result = {"tool": item["tool"], "result": str(item["content"])[:400].replace(str(project), "${PROJECT_DIR}")}
                if entry_result not in mcp_results:
                    mcp_results.append(entry_result)
        shapes = [
            {"instructions_chars": len(instructions_text(r)), "tools": tool_names(r), "input_types": [i.get("type") or i.get("role") for i in r.get("input", []) if isinstance(i, dict)]}
            for r in requests[:6]
        ]
        def _trim(value: Any, limit: int = 1200) -> Any:
            text = value if isinstance(value, str) else json.dumps(value)
            return text[:limit] + ("..." if len(text) > limit else "")
        excerpt = {
            "instructions_head": _trim(instructions_text(first), 600),
            "instructions_tail": instructions_text(first)[-1500:],
            "input": [{k: _trim(v, 1500) for k, v in item.items()} for item in first.get("input", [])[:8] if isinstance(item, dict)],
            "tools": [_trim(t, 1500) for t in first.get("tools", [])],
            "spawn_agent_tool": spawn_tool,
        }
        notes: list[str] = []
        if proc.returncode != 0:
            notes.append(f"codex exit {proc.returncode}: {proc.stderr[-600:]}")
        if not requests:
            notes.append("no request reached the scripted provider")
        result = ProbeResult(
            product=PRODUCT, version=version(), fixture=str(package.root), exit_code=proc.returncode, final_output=final_text,
            entry_instructions_in_instructions=bool(entry_requests),
            entry_instructions_delivered_as=_delivered_as(first, entry_marker), tools_offered_to_entry=offered,
            skill_catalog_advertised_before_activation=catalog, skill_body_absent_before_activation=body_absent_before,
            skill_activated=skill_activated, skill_body_in_context_after_activation=body_after, skill_body_persisted_in_later_turns=body_persisted,
            subagent_tools_offered=[name for name in offered if name in SUBAGENT_TOOLS], subagent_called=called_child,
            subagent_ran_with_own_instructions=bool(child_reqs), subagent_result_returned_to_caller=child_returned,
            subagents_advertised=advertised, mcp_tools_offered=mcp_offered, mcp_tools_by_request=mcp_by_request,
            mcp_log=_mcp_log(proc.stderr, str(project)), mcp_results=mcp_results,
            requests=len(requests), request_shapes=shapes, first_request_excerpt=excerpt,
            stderr_tail=proc.stderr[-6000:], notes=notes,
        )
        return _redacted(result, {str(project): "${PROJECT_DIR}", str(codex_home): "${CODEX_HOME}"})


def _redacted(result: ProbeResult, replacements: dict[str, str]) -> ProbeResult:
    """Replace temporary paths everywhere in the evidence, excerpts included."""

    text = json.dumps(asdict(result))
    for old, new in replacements.items():
        text = text.replace(old, new)
    return ProbeResult(**json.loads(text))


def _extract_agent_id(text: str) -> str | None:
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = None
    if isinstance(data, dict):
        for key in ("agent_id", "id", "thread_id"):
            if key in data:
                return str(data[key])
    import re
    match = re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|[A-Za-z0-9_-]{16,}", str(text))
    return match.group(0) if match else None


def _delivered_as(request: dict[str, Any], marker: str) -> str | None:
    """Where the entry instructions arrived: the instructions field, or a message of some role."""

    if marker in str(request.get("instructions") or ""):
        return "instructions"
    for item in request.get("input", []) or []:
        if isinstance(item, dict) and marker in json.dumps(item):
            head = json.dumps(item.get("content"))[:80]
            return f"{item.get('role', item.get('type'))} message" + (" (AGENTS.md)" if "AGENTS.md" in head else "")
    return None


def _namespaced_function(request: dict[str, Any], name: str) -> dict[str, Any]:
    """The full definition of function `name`, whether top level or inside a namespace tool."""

    for tool in request.get("tools", []) or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("name") == name:
            return tool
        for fn in tool.get("tools", []) if tool.get("type") == "namespace" else []:
            if isinstance(fn, dict) and fn.get("name") == name:
                return fn
    return {}


def _mcp_log(stderr: str, project: str) -> list[str]:
    """Codex log lines about MCP servers: initializations, handshake failures, warnings."""

    keep = []
    for line in stderr.splitlines():
        if "example.com" in line or not any(key in line for key in ("Service initialized", "handshak", "MCP", "mcp_servers", "rmcp_client")):
            continue
        keep.append(line[-400:])
    return keep[:20]
