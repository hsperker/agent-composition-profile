"""GitHub Copilot CLI product probe.

Compiles a package with the copilot target into a temporary project and runs
`copilot -p --agent <entry>` in bring your own key mode, pointed at the
scripted chat completions server. `COPILOT_OFFLINE` disables GitHub
authentication, telemetry, and the built in GitHub MCP server, so no GitHub
account or paid inference is involved.

Isolation: COPILOT_HOME points into the temporary directory, so the user's
configuration, sessions, and MCP servers are neither read nor written.
`COPILOT_ALLOW_ALL=true` (exactly that spelling) trusts the working directory,
which is what loads its `.github/agents`, `.github/skills`, and MCP servers.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..compiler import compile_package
from ..model import Package
from .fake_openai import FakeOpenAI, reply_text, reply_tool_call, system_text, tool_names, tool_results

PRODUCT = "copilot"
UNLISTED_MARKER = "ACP-UNLISTED-SUBAGENT-PROBE"


def available() -> bool:
    return shutil.which("copilot") is not None


def version() -> str:
    try:
        out = subprocess.run(["copilot", "--version"], capture_output=True, text=True, timeout=30).stdout
        return out.splitlines()[0].strip().rstrip(".") if out.strip() else "unknown"
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
    unlisted_subagent_call: str | None
    task_call_results: list[str]
    mcp_events: list[str]
    mcp_servers_status: dict[str, str]
    mcp_tools_offered: list[str]
    mcp_results: list[dict[str, Any]]
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


def _user_text(request: dict[str, Any]) -> str:
    parts = []
    for message in request.get("messages", []):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, list):
                content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
            parts.append(str(content or ""))
    return "\n".join(parts)


def _mcp_tool_names(request: dict[str, Any], servers: list[str]) -> list[str]:
    """Copilot exposes MCP tools as function tools; they are the ones not in its own tool set."""

    names = tool_names(request)
    return sorted(name for name in names if any(server in name for server in servers))


def probe(package: Package, binding: dict[str, Any], *, task: str = "Investigate the claim.", timeout: int = 300) -> ProbeResult:
    entry = package.entry
    child_names = list(entry.subagent_names)
    skill_names = [skill.name for skill in entry.all_skills]
    child_marker = {name: package.agents[name].instructions.strip().splitlines()[-1] for name in child_names}
    entry_marker = entry.instructions.strip().splitlines()[-1]
    unlisted = next((name for name in package.agents if name != entry.name and name not in child_names), entry.name)
    server_names = [server.name for server in entry.mcp_servers]
    result = compile_package(package, PRODUCT, binding, strict=False)

    with tempfile.TemporaryDirectory(prefix="acp-copilot-probe-") as tmp:
        project = (Path(tmp) / "project").resolve()
        home = (Path(tmp) / "copilot-home").resolve()
        project.mkdir()
        home.mkdir()
        _write(result.files, project)
        log = Path(tmp) / "requests.jsonl"

        def director(request: dict[str, Any]) -> dict[str, Any]:
            system = system_text(request)
            names = tool_names(request)
            results = tool_results(request)
            done = {item["tool"] for item in results}
            if UNLISTED_MARKER in _user_text(request):
                return reply_text(f"{unlisted} ran although unlisted")
            for child, marker in child_marker.items():
                if marker in system:
                    return reply_text(f"{child} result: bounded task done")
            if entry_marker not in system:
                return reply_text("unexpected caller")
            if skill_names and "skill" in names and "skill" not in done:
                return reply_tool_call("skill", {"skill": skill_names[0]})
            mcp = [name for name in _mcp_tool_names(request, server_names) if name not in done]
            if mcp:
                return reply_tool_call(mcp[0], {"text": "probe"})
            if child_names and "task" in names and "task" not in done:
                return reply_tool_call("task", {"agent_type": child_names[0], "description": "bounded task",
                                                "prompt": "Analyze this.", "name": "probe-child"})
            if child_names and "task" in names and not any(UNLISTED_MARKER in json.dumps(r) for r in [request]):
                # Second task call: an agent the entry does not list. Tests whether the `agents`
                # allowlist is enforced at call time.
                return reply_tool_call("task", {"agent_type": unlisted, "description": "allowlist probe",
                                                "prompt": UNLISTED_MARKER, "name": "probe-unlisted"})
            return reply_text("final answer from the entry agent")

        with FakeOpenAI(director, log) as fake:
            env = dict(os.environ)
            env.update({
                "COPILOT_HOME": str(home),
                "COPILOT_OFFLINE": "true",
                "COPILOT_ALLOW_ALL": "true",
                "COPILOT_PROVIDER_BASE_URL": fake.base_url,
                "COPILOT_PROVIDER_TYPE": "openai",
                "COPILOT_PROVIDER_API_KEY": "probe-key",
                "COPILOT_MODEL": "probe-model",
                "COPILOT_AUTO_UPDATE": "false",
                "NO_COLOR": "1",
            })
            command = ["copilot", "-p", task, "--agent", entry.name, "--allow-all", "--output-format", "json",
                       "--log-dir", str(Path(tmp) / "logs"), "-C", str(project)]
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
        final_text = next((e["data"].get("content") for e in reversed(events)
                           if e.get("type") == "assistant.message" and e.get("data", {}).get("content")), None)
        status: dict[str, str] = {}
        mcp_events: list[str] = []
        for e in events:
            if e.get("type") == "session.mcp_server_status_changed":
                status[e["data"]["serverName"]] = e["data"]["status"]
            if "mcp" in e.get("type", ""):
                mcp_events.append(json.dumps({"type": e["type"], "data": e.get("data")})[:400])
        errors = [json.dumps(e["data"])[:300] for e in events if e.get("type", "").endswith("error")]

        entry_requests = [r for r in requests if entry_marker in system_text(r) and UNLISTED_MARKER not in _user_text(r)]
        child_requests = {name: [r for r in requests if marker in system_text(r)] for name, marker in child_marker.items()}
        first = entry_requests[0] if entry_requests else {}
        first_blob = json.dumps(first)
        offered = tool_names(first)
        catalog = [name for name in skill_names if name in first_blob]
        # The last entry request carries the whole conversation, so its results are the complete list.
        all_results = tool_results(entry_requests[-1]) if entry_requests else []
        skill_activated = next((skill_names[0] for item in all_results if item["tool"] == "skill"), None) if skill_names else None
        skill_body = entry.all_skills[0].instructions.strip().splitlines()[-1] if entry.all_skills else None
        body_absent_before = bool(skill_body) and skill_body not in first_blob
        after_activation = [json.dumps(r) for r in entry_requests[1:]]
        body_after = bool(skill_body) and any(skill_body in blob for blob in after_activation[:1])
        body_persisted = bool(skill_body) and len(after_activation) > 1 and all(skill_body in blob for blob in after_activation)
        task_results = [item for item in all_results if item["tool"] == "task"]
        called_child = child_names[0] if child_names and task_results else None
        child_reqs = child_requests.get(called_child or "", [])
        child_tools = tool_names(child_reqs[0]) if child_reqs else []
        child_returned = called_child is not None and any(f"{called_child} result" in str(item["content"]) for item in task_results)
        task_tool = next((t.get("function", {}) for t in first.get("tools", []) if t.get("function", {}).get("name") == "task"), {})
        advertised = [name for name in package.agents if f"**{name}**" in (task_tool.get("description") or "")]
        unlisted_call = None
        if len(task_results) > 1:
            content = str(task_results[1]["content"])
            unlisted_call = ("ran" if f"{unlisted} ran although unlisted" in content else "refused") + f": {content[:200]}"
        mcp_offered = _mcp_tool_names(first, server_names) if server_names else []
        mcp_results: list[dict[str, Any]] = []
        for item in all_results:
            if item["tool"] in mcp_offered:
                entry_result = {"tool": item["tool"], "result": str(item["content"])[:400]}
                if entry_result not in mcp_results:
                    mcp_results.append(entry_result)
        notes = [f"copilot error: {error}" for error in errors]
        if proc.returncode != 0:
            notes.append(f"copilot exit {proc.returncode}: {proc.stderr[-600:]}")
        if not requests:
            notes.append("no request reached the scripted provider")
        probe_result = ProbeResult(
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
            unlisted_subagent_call=unlisted_call,
            task_call_results=[str(item["content"])[:300] for item in task_results],
            mcp_events=mcp_events,
            mcp_servers_status=status,
            mcp_tools_offered=mcp_offered,
            mcp_results=mcp_results,
            requests=len(requests),
            notes=notes,
        )
        text = json.dumps(asdict(probe_result)).replace(str(project), "${PROJECT_DIR}").replace(str(home), "${COPILOT_HOME}")
        return ProbeResult(**json.loads(text))
