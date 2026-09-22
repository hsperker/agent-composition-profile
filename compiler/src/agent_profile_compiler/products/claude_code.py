"""Claude Code product probe.

Compiles a package with the claude-code target into a temporary project,
runs `claude -p --agent <entry>` headless against the scripted Anthropic
server, and reports what reached the model: the agent's instructions, skill
metadata and activation, plugin MCP tools and their results, and the subagent
call and its returned result.

Claude Code is redirected with ANTHROPIC_BASE_URL and given a fresh
CLAUDE_CONFIG_DIR in which only the temporary project is marked trusted, so the
user's own configuration and login are untouched.
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
from .fake_anthropic import FakeAnthropic, system_text, text, tool_names, tool_results, tool_use

PRODUCT = "claude-code"


def available() -> bool:
    return shutil.which("claude") is not None


def version() -> str:
    try:
        return subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
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


def probe(package: Package, binding: dict[str, Any], *, task: str = "Investigate the claim.", timeout: int = 240) -> ProbeResult:
    """Run one package through Claude Code with a scripted model and report what happened."""

    entry = package.entry
    child_names = list(entry.subagent_names)
    skill_names = [skill.name for skill in entry.all_skills]
    child_marker = {name: package.agents[name].instructions.strip().splitlines()[-1] for name in child_names}
    entry_marker = entry.instructions.strip().splitlines()[-1]
    result = compile_package(package, PRODUCT, binding, strict=False)

    with tempfile.TemporaryDirectory(prefix="acp-claude-probe-") as tmp:
        # Claude Code keys project trust by the resolved path (macOS symlinks /var to /private/var).
        project = (Path(tmp) / "project").resolve()
        config_dir = (Path(tmp) / "config").resolve()
        project.mkdir()
        config_dir.mkdir()
        _write(result.files, project)
        # Claude Code blocks agent-level MCP servers until the project is trusted. The probe
        # marks its temporary project trusted in its own config dir; the user's is untouched.
        (config_dir / ".claude.json").write_text(
            json.dumps({"projects": {str(project): {"hasTrustDialogAccepted": True, "hasCompletedProjectOnboarding": True}}}),
            encoding="utf-8",
        )
        log = Path(tmp) / "requests.jsonl"

        def director(request: dict[str, Any]) -> list[dict[str, Any]]:
            system = system_text(request)
            names = tool_names(request)
            done = {item["tool"] for item in tool_results(request)}
            for child, marker in child_marker.items():
                if marker in system:
                    return [text(f"{child} result: bounded task done")]
            if entry_marker not in system:
                return [text("unexpected caller")]
            if skill_names and "Skill" in names and "Skill" not in done:
                return [tool_use("Skill", {"skill": skill_names[0]})]
            mcp = [name for name in names if name.startswith("mcp__") and name not in done]
            if mcp:
                return [tool_use(mcp[0], {"text": "probe"})]
            if child_names and "Agent" in names and "Agent" not in done:
                return [tool_use("Agent", {"subagent_type": child_names[0], "description": "bounded task", "prompt": "Analyze this."})]
            return [text("final answer from the entry agent")]

        with FakeAnthropic(director, log) as fake:
            env = dict(os.environ)
            env.update({
                "ANTHROPIC_BASE_URL": fake.base_url,
                "ANTHROPIC_API_KEY": "probe-key",
                "CLAUDE_CONFIG_DIR": str(config_dir),
                "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                "DISABLE_TELEMETRY": "1",
                "DISABLE_AUTOUPDATER": "1",
                "DISABLE_ERROR_REPORTING": "1",
            })
            command = [
                "claude", "-p", task, "--agent", entry.name, "--output-format", "json",
                "--dangerously-skip-permissions", "--no-session-persistence",
                "--setting-sources", "project", "--model", "claude-probe",
            ]
            proc = subprocess.run(command, cwd=project, env=env, capture_output=True, text=True,
                                  timeout=timeout, stdin=subprocess.DEVNULL)
            requests = [item["request"] for item in fake.requests()]

        output: dict[str, Any] = {}
        if proc.stdout.strip().startswith("{"):
            try:
                output = json.loads(proc.stdout)
            except json.JSONDecodeError:
                output = {}
        entry_requests = [r for r in requests if entry_marker in system_text(r)]
        child_requests = {name: [r for r in requests if marker in system_text(r)] for name, marker in child_marker.items()}
        first = entry_requests[0] if entry_requests else {}
        offered = tool_names(first)
        # Claude Code lists skills and agent types in system-reminder messages inside the
        # conversation, so the catalog check covers the whole first request.
        first_blob = json.dumps(first)
        catalog = [name for name in skill_names if name in first_blob]
        all_results = [item for r in entry_requests for item in tool_results(r)]
        skill_activated = next((skill_names[0] for item in all_results if item["tool"] == "Skill"), None) if skill_names else None
        skill_body = entry.all_skills[0].instructions.strip().splitlines()[-1] if entry.all_skills else None
        body_absent_before = bool(skill_body) and skill_body not in first_blob
        after_activation = [json.dumps(r) for r in entry_requests[1:]]
        body_after = bool(skill_body) and any(skill_body in blob for blob in after_activation[:1])
        body_persisted = bool(skill_body) and len(after_activation) > 1 and all(skill_body in blob for blob in after_activation)
        called_child = next((child_names[0] for item in all_results if item["tool"] == "Agent"), None) if child_names else None
        child_reqs = child_requests.get(called_child or "", [])
        child_ran = bool(child_reqs)
        child_tools = tool_names(child_reqs[0]) if child_reqs else []
        child_returned = called_child is not None and any(f"{called_child} result" in json.dumps(r) for r in entry_requests)
        mcp_offered = sorted(name for name in offered if name.startswith("mcp__"))
        mcp_results: list[dict[str, Any]] = []
        for item in all_results:  # later requests repeat earlier tool results; keep each once
            if item["tool"].startswith("mcp__"):
                entry_result = {"tool": item["tool"], "result": str(item["content"])[:400].replace(str(project), "${PROJECT_DIR}")}
                if entry_result not in mcp_results:
                    mcp_results.append(entry_result)
        notes: list[str] = []
        if output.get("is_error"):
            notes.append(f"claude reported an error: {output.get('result')}")
        stats = output.get("subagent_stats") or {}
        if stats:
            notes.append(f"subagent_stats spawned={stats.get('spawned')} completed={stats.get('completed')}")
        return ProbeResult(
            product=PRODUCT, version=version(), fixture=str(package.root),
            exit_code=proc.returncode, final_output=output.get("result"),
            entry_instructions_in_system_prompt=bool(entry_requests),
            tools_offered_to_entry=offered,
            skill_catalog_advertised_before_activation=catalog,
            skill_body_absent_before_activation=body_absent_before,
            skill_activated=skill_activated,
            skill_body_in_context_after_activation=body_after,
            skill_body_persisted_in_later_turns=body_persisted,
            subagent_called=called_child,
            subagent_ran_with_own_instructions=child_ran,
            subagent_tools_offered=child_tools,
            subagent_result_returned_to_caller=child_returned,
            mcp_tools_offered=mcp_offered,
            mcp_results=mcp_results,
            requests=len(requests),
            notes=notes,
        )
