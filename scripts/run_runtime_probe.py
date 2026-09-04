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
from agent_profile_compiler.runtime.registry import RUNTIME_TARGETS, load_runtime_adapter


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "research-team"
DELEGATION = ROOT / "examples" / "runtime-probes" / "delegation"
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
    artifact = adapter.build(package, binding, strict=target in {"openai-agents", "microsoft-agent-framework"})
    return "delegation", artifact, adapter.run(artifact, "Solve the problem.")


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
    print(f"generated {target}: strict={strict_result['outcome']} runtime={run.output!r}")


if __name__ == "__main__":
    main()
