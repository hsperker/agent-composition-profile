#!/usr/bin/env python3
"""Generate one framework's evidence in its isolated pinned environment."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import runpy

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError
from agent_profile_compiler.runtime.mcp_probe import ECHO_TASK, echo_http_server, parse_echo_result
from agent_profile_compiler.runtime.registry import RUNTIME_TARGETS, load_runtime_adapter


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "research-team"
DELEGATION = ROOT / "examples" / "runtime-probes" / "delegation"
ACTIVATION = ROOT / "examples" / "runtime-probes" / "plugin-activation"
ACTIVATION_PLUGIN_ROOT = (ACTIVATION / "plugins" / "local-echo").resolve()
TEST_FILES = {
    "langgraph": "test_langgraph_runtime.py",
    "crewai": "test_crewai_runtime.py",
    "llamaindex": "test_llamaindex_runtime.py",
    "agno": "test_agno_runtime.py",
    "openai-agents": "test_openai_agents_runtime.py",
    "google-adk": "test_google_adk_runtime.py",
    "pydantic-ai": "test_pydantic_ai_runtime.py",
    "microsoft-agent-framework": "test_microsoft_agent_framework_runtime.py",
}


def load_fixture_namespace(target: str) -> dict:
    path = ROOT / "compiler" / "tests" / "runtime" / TEST_FILES[target]
    return runpy.run_path(str(path), run_name=f"_runtime_probe_{target.replace('-', '_')}")


def research_binding(target: str, ns: dict, package) -> dict:
    if target == "langgraph":
        return ns["bindings"]()
    if target in {"crewai", "llamaindex", "agno"}:
        return ns["binding"]()
    if target == "openai-agents":
        return ns["binding"]({name: ns["ScriptedModel"]() for name in package.agents})
    if target == "google-adk":
        models = {
            name: ns["ScriptedLlm"](
                model=f"scripted-{name}", responses=[ns["text_response"]("unused")]
            )
            for name in package.agents
        }
        return ns["binding"](models)
    if target == "pydantic-ai":
        models = {
            name: ns["TestModel"](custom_output_text=f"unused-{name}")
            for name in package.agents
        }
        return ns["binding"](models)
    if target == "microsoft-agent-framework":
        clients = {
            name: ns["ScriptedChatClient"]([ns["text_response"](f"unused-{name}")])
            for name in package.agents
        }
        return ns["binding"](clients)
    raise AssertionError(target)


def runtime_probe(target: str, ns: dict, adapter):
    if target == "langgraph":
        package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
        artifact = adapter.build(package, ns["bindings"](), strict=False)
        return "research-team", artifact, adapter.run(artifact, "Investigate the claim.")
    if target in {"crewai", "llamaindex", "agno"}:
        package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)
        artifact = adapter.build(package, ns["binding"](), strict=False)
        return "research-team/critic", artifact, adapter.run(artifact, "Challenge this conclusion.")

    package = load_package(DELEGATION / "lead.agent.md", DELEGATION)
    if target == "openai-agents":
        worker = ns["ScriptedModel"]([[ns["assistant_message"]("worker result")]])
        coordinator = ns["ScriptedModel"](
            [
                [ns["function_call"]("worker", {"input": "Analyze this."}, call_id="call-1")],
                [ns["assistant_message"]("coordinator used worker result")],
            ]
        )
        binding = ns["binding"]({"coordinator": coordinator, "worker": worker})
    elif target == "google-adk":
        worker = ns["ScriptedLlm"](
            model="scripted-worker", responses=[ns["text_response"]("worker result")]
        )
        coordinator = ns["ScriptedLlm"](
            model="scripted-coordinator",
            responses=[
                ns["function_response"]("worker", "Analyze this."),
                ns["text_response"]("coordinator used worker result"),
            ],
        )
        binding = ns["binding"]({"coordinator": coordinator, "worker": worker})
    elif target == "pydantic-ai":
        binding = ns["binding"](
            {
                "coordinator": ns["TestModel"](
                    call_tools=["worker"], custom_output_text="coordinator used worker result"
                ),
                "worker": ns["TestModel"](custom_output_text="worker result"),
            }
        )
    elif target == "microsoft-agent-framework":
        binding = ns["binding"](
            {
                "coordinator": ns["ScriptedChatClient"](
                    [
                        ns["function_response"]("worker", "Analyze this."),
                        ns["text_response"]("coordinator used worker result"),
                    ]
                ),
                "worker": ns["ScriptedChatClient"]([ns["text_response"]("worker result")]),
            }
        )
    else:
        raise AssertionError(target)
    artifact = adapter.build(package, binding, strict=target in {"openai-agents", "pydantic-ai", "microsoft-agent-framework"})
    return "delegation", artifact, adapter.run(artifact, "Solve the problem.")


def activation_model(target: str, ns: dict):
    if target == "langgraph":
        return ns["EchoCallingModel"]()
    if target == "crewai":
        return ns["EchoCallingCrewLLM"](model="echo-caller")
    if target == "llamaindex":
        return ns["echo_calling_model"]()
    if target == "agno":
        return ns["EchoCallingAgnoModel"](id="echo-caller")
    if target == "openai-agents":
        return ns["EchoCallingModel"]()
    if target == "google-adk":
        return ns["EchoCallingLlm"](model="echo-caller")
    if target == "pydantic-ai":
        return ns["TestModel"](call_tools="all", custom_output_text="echo done")
    if target == "microsoft-agent-framework":
        return ns["EchoCallingChatClient"]()
    raise AssertionError(target)


def activation_probe(target: str, ns: dict, adapter) -> dict:
    """Activate the plugin-activation fixture end to end and summarize per server."""

    package = load_package(ACTIVATION / "agent.agent.md", ACTIVATION)
    entry = package.entry
    binding = {"capabilities": {}, "models": {entry.name: activation_model(target, ns)}, "activate_plugins": True}
    label_to_server = {
        ("stdio" if server.config["type"] == "stdio" else "http"): server.name for server in entry.mcp_servers
    }
    summary: dict[str, dict] = {
        server.name: {
            "transport": server.config["type"],
            "status": "failed",
            "tools_as_seen": [],
            "result": None,
            "error": None,
        }
        for server in entry.mcp_servers
    }
    observations: list[dict] = []
    output = None
    error = None
    try:
        with echo_http_server(ACTIVATION_PLUGIN_ROOT):
            artifact = adapter.build(package, binding, strict=False)
            plugin_findings = {
                finding.feature: finding.status
                for finding in artifact.report.findings
                if finding.agent == entry.name and finding.feature.startswith("plugins")
            }
            run = adapter.run(artifact, ECHO_TASK, activate_plugins=True)
        output = run.output
        observations = [item.to_dict() for item in run.observations]
        for item in run.observations:
            if item.kind == "mcp-tools-discovered":
                if item.data["server"] in summary:
                    summary[item.data["server"]]["tools_as_seen"] = list(item.data["tools"])
                else:  # CrewAI cannot attribute tools to a server
                    for server in summary.values():
                        server["tools_as_seen"] = list(item.data["tools"])
                        server["tool_attribution"] = item.data.get("note")
            if item.kind == "mcp-activation-failed" and item.data["server"] in summary:
                summary[item.data["server"]]["error"] = item.data["error"]
            if item.kind == "mcp-tool-result":
                payload = parse_echo_result(item.data["result"])
                server_name = item.data["server"]
                if server_name not in summary:
                    server_name = label_to_server.get(payload.get("label"), server_name)
                if server_name in summary and "label" in payload:
                    entry_summary = summary[server_name]
                    entry_summary["status"] = "activated"
                    entry_summary["result"] = payload
                    if entry_summary["transport"] == "stdio":
                        entry_summary["cwd_honored"] = payload.get("cwd") == str(ACTIVATION_PLUGIN_ROOT)
                        entry_summary["env_honored"] = bool(payload.get("plugin_root_env")) and bool(
                            payload.get("plugin_data_env")
                        )
                    else:
                        entry_summary["header_honored"] = True
    except Exception as exc:  # the probe itself must never hide a failure
        error = f"{type(exc).__name__}: {exc}"
        plugin_findings = {}
    return {
        "target": target,
        "fixture": "examples/runtime-probes/plugin-activation",
        "chain": ["construct", "handshake", "discover", "invoke", "result"],
        "construction_findings": plugin_findings,
        "servers": summary,
        "output": output,
        "error": error,
        "observations": observations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=RUNTIME_TARGETS)
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated" / "runtime")
    args = parser.parse_args()

    target = args.target
    spec = RUNTIME_TARGETS[target]
    actual_version = importlib.metadata.version(spec.distribution)
    if actual_version != spec.version:
        raise SystemExit(
            f"wrong {spec.distribution} version: expected {spec.version}, got {actual_version}"
        )
    ns = load_fixture_namespace(target)
    adapter = load_runtime_adapter(target)
    research = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    binding = research_binding(target, ns, research)
    artifact = adapter.build(research, binding, strict=False)

    strict_result: dict[str, object]
    try:
        adapter.build(research, research_binding(target, ns, research), strict=True)
    except RuntimeCompatibilityError as exc:
        strict_result = {"outcome": "rejected", "reason": str(exc)}
    else:
        strict_result = {"outcome": "accepted"}

    probe_name, probe_artifact, run = runtime_probe(target, ns, adapter)
    output_dir = args.output_root / target
    output_dir.mkdir(parents=True, exist_ok=True)
    compatibility = artifact.report.to_dict()
    compatibility.update(
        {
            "tested_distribution": spec.distribution,
            "tested_version": actual_version,
            "requirements_lock": str(spec.requirements.relative_to(ROOT)),
            "requirements_sha256": hashlib.sha256(spec.requirements.read_bytes()).hexdigest(),
            "strict_mode": strict_result,
            "construction_observations": [item.to_dict() for item in artifact.observations],
        }
    )
    runtime = {
        "target": target,
        "probe": probe_name,
        "output": run.output,
        "observations": [item.to_dict() for item in run.observations],
        "native_types": {
            name: f"{type(native).__module__}.{type(native).__name__}"
            for name, native in probe_artifact.native_agents.items()
        },
    }
    (output_dir / "compatibility.json").write_text(
        json.dumps(compatibility, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_dir / "runtime.json").write_text(
        json.dumps(runtime, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    activation = activation_probe(target, ns, adapter)
    (output_dir / "plugin-activation.json").write_text(
        json.dumps(activation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    statuses = ", ".join(f"{name}={server['status']}" for name, server in activation["servers"].items())
    print(
        f"generated {target}: strict={strict_result['outcome']} runtime={run.output!r} "
        f"activation=[{statuses}]"
    )


if __name__ == "__main__":
    main()
