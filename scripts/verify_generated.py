from __future__ import annotations

import json
import hashlib
from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "generated"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3:
        raise AssertionError(f"{path}: missing frontmatter delimiters")
    value = yaml.safe_load(parts[1])
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: frontmatter is not a mapping")
    return value


def report(name: str) -> dict:
    return json.loads((GENERATED / name / "compatibility-report.json").read_text(encoding="utf-8"))


def main() -> None:
    # Parse every generated machine-readable artifact.
    for path in GENERATED.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in GENERATED.rglob("*.toml"):
        tomllib.loads(path.read_text(encoding="utf-8"))
    for path in GENERATED.rglob("*.md"):
        if path.name == "SKILL.md" or path.name.endswith((".agent.md", ".afm.md")) or path.name in {"bundle.md", "critic.md", "explorer.md", "lead-researcher.md"}:
            frontmatter(path)
    for path in GENERATED.rglob("*.yaml"):
        yaml.safe_load(path.read_text(encoding="utf-8"))

    expected = {
        "amplifier-critic-strict": False,
        "amplifier-full-diagnostic": True,
        "claude-code-full-strict": False,
        "codex-full-strict": False,
        "copilot-full-strict": False,
        "opencode-full-strict": False,
        "afm-explorer-strict": False,
        "afm-full-diagnostic": True,
    }
    for name, has_unsupported in expected.items():
        payload = report(name)
        assert payload["has_unsupported"] is has_unsupported, (name, payload["summary"])
        assert payload["has_blocking_loss"] is has_unsupported, (name, payload["summary"])

    claude = frontmatter(
        GENERATED / "claude-code-full-strict/.claude/agents/lead-researcher.md"
    )
    assert "Agent(explorer, critic)" in claude["tools"]
    assert "mcp__research__*" in claude["tools"]

    codex = tomllib.loads(
        (GENERATED / "codex-full-strict/.codex/agents/lead-researcher.toml").read_text(
            encoding="utf-8"
        )
    )
    assert "skills" not in codex
    assert "research" in codex["mcp_servers"]
    assert (GENERATED / "codex-full-strict/.agents/skills/source-evaluation/SKILL.md").is_file()

    copilot = frontmatter(GENERATED / "copilot-full-strict/.github/agents/lead-researcher.agent.md")
    assert copilot["agents"] == ["explorer", "critic"]
    assert "research" in copilot["mcp-servers"]
    json.loads((GENERATED / "copilot-full-strict/.vscode/mcp.json").read_text(encoding="utf-8"))
    opencode = frontmatter(GENERATED / "opencode-full-strict/.opencode/agent/lead-researcher.md")
    assert opencode["permission"]["task"]["explorer"] == "allow"
    assert "research" in json.loads((GENERATED / "opencode-full-strict/opencode.json").read_text(encoding="utf-8"))["mcp"]

    amplifier = frontmatter(GENERATED / "amplifier-critic-strict/agents/critic.md")
    assert amplifier["meta"]["model_role"] == "reasoning"
    assert amplifier["agents"] == "none"

    afm = frontmatter(GENERATED / "afm-explorer-strict/explorer.afm.md")
    assert afm["spec_version"] == "0.4.0"
    assert afm["tools"]["mcp"][0]["transport"]["type"] == "http"

    runtime_reports = list((GENERATED / "runtime").glob("*/compatibility.json"))
    assert len(runtime_reports) == 8
    allowed = {"preserved", "resolved", "approximated", "unsupported", "omitted-preference", "unverified"}
    modules = {"core", "description", "model", "skills", "plugins", "subagents"}
    expected_strict = {
        "langgraph": "rejected",
        "crewai": "rejected",
        "llamaindex": "rejected",
        "agno": "rejected",
        "openai-agents": "accepted",
        "google-adk": "rejected",
        "pydantic-ai": "accepted",
        "microsoft-agent-framework": "accepted",
    }
    for path in runtime_reports:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["tested_version"]
        assert payload["strict_mode"]["outcome"] == expected_strict[payload["target"]], payload["target"]
        assert all(finding["status"] in allowed for finding in payload["findings"])
        assert set(payload["modules"]) == modules, payload["target"]
        assert payload["modules"]["skills"]["unverified"], payload["target"]
        test_output = path.with_name("test-output.txt").read_text(encoding="utf-8")
        assert "100%" in test_output
        assert "failed" not in test_output.lower()

    activation_reports = list((GENERATED / "runtime").glob("*/plugin-activation.json"))
    assert len(activation_reports) == 8
    for path in activation_reports:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["error"] is None, (payload["target"], payload["error"])
        assert set(payload["servers"]) == {"echostdio", "echohttp"}
        for name, server in payload["servers"].items():
            assert server["status"] == "activated", (payload["target"], name, server)
        assert payload["servers"]["echostdio"]["env_honored"] is True, payload["target"]
        assert payload["servers"]["echohttp"]["header_honored"] is True, payload["target"]

    product_probes = sorted((GENERATED / "products").glob("*/probe-*.json")) if (GENERATED / "products").exists() else []
    for path in product_probes:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["exit_code"] == 0, (path, payload["notes"])
        assert payload["entry_instructions_in_system_prompt"] is True, path
        if path.stem.endswith("research-team"):
            assert payload["skill_activated"] and payload["skill_body_absent_before_activation"], path
            assert payload["skill_body_in_context_after_activation"] and payload["skill_body_persisted_in_later_turns"], path
            assert payload["subagent_called"] and payload["subagent_ran_with_own_instructions"], path
            assert payload["subagent_result_returned_to_caller"], path
        if path.stem.endswith("plugin-activation"):
            if payload["product"] == "claude-code":
                assert len(payload["mcp_tools_offered"]) == 2 and len(payload["mcp_results"]) == 2, path
            if payload["product"] == "opencode":
                assert payload["mcp_servers_connected"] == {"echostdio": "connected", "echohttp": "connected"}, path
                if path.parent.name.endswith("-v2"):
                    assert payload["mcp_tools_offered"] == [], path
                else:
                    assert len(payload["mcp_tools_offered"]) == 2 and len(payload["mcp_results"]) == 2, path
        assert "hans-christian" not in path.read_text(encoding="utf-8"), path

    matrix = json.loads((GENERATED / "runtime/matrix.json").read_text(encoding="utf-8"))
    assert len(matrix["targets"]) == 14
    assert sum(kind == "runtime" for kind in matrix["evidence_kind"].values()) == 8
    assert sum(kind == "product-static" for kind in matrix["evidence_kind"].values()) == 6
    expected_hashes = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "examples/research-team").rglob("*"))
        if path.is_file()
    }
    assert matrix["source_fixture_sha256"] == expected_hashes
    assert set(matrix["modules"]) == set(matrix["targets"])
    assert len(matrix["plugin_activation"]) == 8
    assert all(set(outcomes) == modules for outcomes in matrix["modules"].values())
    assert (GENERATED / "runtime/matrix.md").is_file()

    print("generated artifacts verified")


if __name__ == "__main__":
    main()
