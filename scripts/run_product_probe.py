#!/usr/bin/env python3
"""Run one product CLI headless against a scripted model and record what reached it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.products import claude_code
from agent_profile_compiler.runtime.mcp_probe import echo_http_server

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "research-team": ROOT / "examples" / "research-team" / "lead.agent.md",
    "plugin-activation": ROOT / "examples" / "runtime-probes" / "plugin-activation" / "agent.agent.md",
}
PRODUCTS = {"claude-code": claude_code}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("product", choices=sorted(PRODUCTS))
    parser.add_argument("--output-root", type=Path, default=ROOT / "generated" / "products")
    args = parser.parse_args()
    module = PRODUCTS[args.product]
    if not module.available():
        raise SystemExit(f"{args.product} is not installed; skipping the product probe")

    output_dir = args.output_root / args.product
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, entry in FIXTURES.items():
        package = load_package(entry, entry.parent)
        binding = {"capabilities": {"reasoning": True, "tool-use": True}, "entry_mode": "main"}
        if name == "plugin-activation":
            plugin_root = (entry.parent / "plugins" / "local-echo").resolve()
            with echo_http_server(plugin_root):
                result = module.probe(package, binding)
        else:
            result = module.probe(package, binding)
        payload = result.to_dict()
        payload["fixture"] = str(entry.parent.relative_to(ROOT))
        payload = json.loads(json.dumps(payload).replace(str(ROOT), "${REPO_ROOT}"))
        (output_dir / f"probe-{name}.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"{args.product} {name}: exit={result.exit_code} instructions={result.entry_instructions_in_system_prompt} "
            f"skill={result.skill_activated} subagent={result.subagent_called} returned={result.subagent_result_returned_to_caller} "
            f"mcp={result.mcp_tools_offered} mcp_results={len(result.mcp_results)}"
        )


if __name__ == "__main__":
    main()
