from pathlib import Path
import json
import shutil
import tomllib

import pytest
import yaml

from agent_profile_compiler.compiler import CompilationError, compile_package
from agent_profile_compiler.parser import load_package


ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "examples" / "research-team"
BINDINGS = yaml.safe_load((ROOT / "bindings" / "example-bindings.yaml").read_text(encoding="utf-8"))["targets"]


def statuses(result, feature: str, agent: str | None = None) -> set[str]:
    return {
        finding.status
        for finding in result.report.findings
        if finding.feature == feature and (agent is None or finding.agent == agent)
    }


def test_amplifier_preserves_leaf_identity_instructions_and_model_role() -> None:
    package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)
    result = compile_package(package, "amplifier", BINDINGS["amplifier"], strict=True)

    generated = result.files["agents/critic.md"]
    frontmatter = yaml.safe_load(generated.split("---", 2)[1])
    assert frontmatter["meta"]["name"] == "critic"
    assert frontmatter["meta"]["model_role"] == "reasoning"
    assert frontmatter["agents"] == "none"
    assert "Try to falsify the tentative conclusion." in generated
    assert statuses(result, "name", "critic") == {"preserved"}
    assert statuses(result, "description", "critic") == {"preserved"}
    assert statuses(result, "model.requires.reasoning", "critic") == {"resolved"}


def test_amplifier_full_package_reports_skill_and_plugin_runtime_gaps() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    result = compile_package(package, "amplifier", BINDINGS["amplifier"], strict=False)

    lead = yaml.safe_load(result.files["agents/lead-researcher.md"].split("---", 2)[1])
    assert lead["agents"] == ["explorer", "critic"]
    assert statuses(result, "skills", "lead-researcher") == {"unsupported"}
    assert statuses(result, "plugins", "lead-researcher") == {"unsupported"}

    with pytest.raises(CompilationError, match="strict compilation would lose required semantics"):
        compile_package(package, "amplifier", BINDINGS["amplifier"], strict=True)


def test_claude_code_lowers_full_package_with_scoped_mcp_and_main_agent_delegate_allowlist() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    result = compile_package(package, "claude-code", BINDINGS["claude-code"], strict=True)

    lead_text = result.files[".claude/agents/lead-researcher.md"]
    lead_frontmatter = yaml.safe_load(lead_text.split("---", 2)[1])
    assert lead_frontmatter["model"] == "opus"
    assert "Agent(explorer, critic)" in lead_frontmatter["tools"]
    assert "Skill" in lead_frontmatter["tools"]
    assert "mcp__research__*" in lead_frontmatter["tools"]
    assert lead_frontmatter["mcpServers"][0]["research"]["type"] == "http"
    assert ".claude/skills/source-evaluation/SKILL.md" in result.files
    assert ".claude/skills/query-planning/SKILL.md" in result.files
    assert statuses(result, "delegates", "lead-researcher") == {"preserved"}
    assert statuses(result, "plugins", "lead-researcher") == {"resolved"}
    assert not result.report.has_unsupported


def test_claude_code_rejects_nested_delegate_allowlist_in_strict_mode(tmp_path: Path) -> None:
    # Reuse the package but make explorer delegate to critic; Claude ignores Agent(type) in subagents.
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    for source in EXAMPLE.rglob("*"):
        if source.is_file():
            target = package_dir / source.relative_to(EXAMPLE)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    explorer = package_dir / "agents" / "explorer.agent.md"
    text = explorer.read_text(encoding="utf-8").replace(
        "plugins:\n  - ../plugins/web-research\n",
        "plugins:\n  - ../plugins/web-research\ndelegates:\n  - ./critic.agent.md\n",
    )
    explorer.write_text(text, encoding="utf-8")
    package = load_package(package_dir / "lead.agent.md", package_dir)

    result = compile_package(package, "claude-code", BINDINGS["claude-code"], strict=False)
    assert statuses(result, "delegates", "explorer") == {"unsupported"}
    with pytest.raises(CompilationError):
        compile_package(package, "claude-code", BINDINGS["claude-code"], strict=True)


def test_codex_emits_parseable_agent_toml_and_resolves_delegate_catalog() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    result = compile_package(package, "codex", BINDINGS["codex"], strict=True)

    lead = tomllib.loads(result.files[".codex/agents/lead-researcher.toml"])
    assert lead["name"] == "lead-researcher"
    assert lead["model"] == "gpt-5.6-terra"
    assert lead["model_reasoning_effort"] == "high"
    assert "skills" not in lead
    assert lead["mcp_servers"]["research"]["url"] == "https://research.example.com/mcp"
    assert "explorer" in lead["developer_instructions"]
    assert "critic" in lead["developer_instructions"]
    assert statuses(result, "delegates", "lead-researcher") == {"resolved"}
    assert not result.report.has_unsupported


def test_afm_compiles_leaf_with_skill_and_plugin_mcp_but_rejects_local_delegates() -> None:
    leaf = load_package(EXAMPLE / "agents" / "explorer.agent.md", EXAMPLE)
    leaf_result = compile_package(leaf, "afm", BINDINGS["afm"], strict=True)
    afm_text = leaf_result.files["explorer.afm.md"]
    frontmatter = yaml.safe_load(afm_text.split("---", 2)[1])
    assert frontmatter["spec_version"] == "0.4.0"
    assert frontmatter["skills"] == [
        {"type": "local", "path": "./skills/source-evaluation"},
        {"type": "local", "path": "./skills/query-planning"},
    ]
    assert frontmatter["tools"]["mcp"][0]["transport"]["type"] == "http"
    assert "# Role" in afm_text and "# Instructions" in afm_text

    full = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    diagnostic = compile_package(full, "afm", BINDINGS["afm"], strict=False)
    assert statuses(diagnostic, "delegates", "lead-researcher") == {"unsupported"}
    with pytest.raises(CompilationError):
        compile_package(full, "afm", BINDINGS["afm"], strict=True)



def test_afm_reports_agent_plugin_http_headers_as_unrepresentable(tmp_path: Path) -> None:
    package_root = tmp_path / "research-team"
    shutil.copytree(EXAMPLE, package_root)
    mcp_path = package_root / "plugins" / "web-research" / "mcp.json"
    mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
    mcp["mcpServers"]["research"]["headers"] = {"X-Research-Mode": "primary-sources"}
    mcp_path.write_text(json.dumps(mcp), encoding="utf-8")

    package = load_package(package_root / "agents" / "explorer.agent.md", package_root)
    result = compile_package(package, "afm", BINDINGS["afm"], strict=False)

    assert statuses(result, "plugins", "explorer") == {"unsupported"}
    generated = yaml.safe_load(result.files["explorer.afm.md"].split("---", 2)[1])
    assert "headers" not in generated["tools"]["mcp"][0]["transport"]

    with pytest.raises(CompilationError):
        compile_package(package, "afm", BINDINGS["afm"], strict=True)

def test_every_compiler_result_has_machine_readable_report() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    result = compile_package(package, "amplifier", BINDINGS["amplifier"], strict=False)

    payload = json.loads(result.files["compatibility-report.json"])
    assert payload["target"] == "amplifier"
    assert payload["source_entry"] == "lead-researcher"
    assert any(item["status"] == "unsupported" for item in payload["findings"])


def test_codex_uses_repository_skill_discovery_instead_of_invalid_relative_skills_config() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    result = compile_package(package, "codex", BINDINGS["codex"], strict=True)

    lead = tomllib.loads(result.files[".codex/agents/lead-researcher.toml"])
    assert "skills" not in lead
    assert ".agents/skills/source-evaluation/SKILL.md" in result.files
    assert ".agents/skills/query-planning/SKILL.md" in result.files
    assert statuses(result, "skills", "lead-researcher") == {"resolved"}


def test_claude_rejects_global_skill_name_collision_that_cannot_be_copied_once(tmp_path: Path) -> None:
    package_root = tmp_path / "package"
    write_skill = lambda root, name: (
        root.mkdir(parents=True, exist_ok=True),
        (root / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Skill {name}.\n---\n\nUse it.\n",
            encoding="utf-8",
        ),
    )
    write_skill(package_root / "left" / "skills" / "shared", "shared")
    write_skill(package_root / "right" / "skills" / "shared", "shared")
    write_agent = lambda path, frontmatter: (
        path.parent.mkdir(parents=True, exist_ok=True),
        path.write_text(f"---\n{frontmatter}\n---\n\n# Instructions\n\nDo the work.\n", encoding="utf-8"),
    )
    write_agent(
        package_root / "root.agent.md",
        "name: root-agent\ndescription: Coordinates two agents.\ndelegates: [./left.agent.md, ./right.agent.md]",
    )
    write_agent(
        package_root / "left.agent.md",
        "name: left-agent\ndescription: Uses the left skill.\nskills: [./left/skills/shared]",
    )
    write_agent(
        package_root / "right.agent.md",
        "name: right-agent\ndescription: Uses the right skill.\nskills: [./right/skills/shared]",
    )
    package = load_package(package_root / "root.agent.md", package_root)

    result = compile_package(package, "claude-code", BINDINGS["claude-code"], strict=False)
    assert statuses(result, "skills", "left-agent") == {"unsupported"}
    assert statuses(result, "skills", "right-agent") == {"unsupported"}
    with pytest.raises(CompilationError):
        compile_package(package, "claude-code", BINDINGS["claude-code"], strict=True)


def test_amplifier_emits_a_loadable_bundle_layout_for_leaf_agent() -> None:
    package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)
    result = compile_package(package, "amplifier", BINDINGS["amplifier"], strict=True)

    bundle = result.files["bundle.md"]
    bundle_frontmatter = yaml.safe_load(bundle.split("---", 2)[1])
    assert bundle_frontmatter["bundle"]["name"] == "research-team"
    assert "research-team:behaviors/agents" in [item["bundle"] for item in bundle_frontmatter["includes"]]
    behavior = yaml.safe_load(result.files["behaviors/agents.yaml"])
    assert behavior["agents"]["include"] == ["research-team:critic"]
    assert "behavior.yaml" not in result.files


def test_codex_rejects_agent_plugin_sse_transport_in_strict_mode(tmp_path: Path) -> None:
    package_root = tmp_path / "research-team"
    shutil.copytree(EXAMPLE, package_root)
    mcp_path = package_root / "plugins" / "web-research" / "mcp.json"
    mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
    mcp["mcpServers"]["research"] = {
        "type": "sse",
        "url": "https://research.example.com/events",
    }
    mcp_path.write_text(json.dumps(mcp), encoding="utf-8")

    package = load_package(package_root / "lead.agent.md", package_root)
    result = compile_package(package, "codex", BINDINGS["codex"], strict=False)

    assert statuses(result, "plugins", "lead-researcher") == {"unsupported"}
    lead = tomllib.loads(result.files[".codex/agents/lead-researcher.toml"])
    assert "mcp_servers" not in lead

    with pytest.raises(CompilationError):
        compile_package(package, "codex", BINDINGS["codex"], strict=True)


def test_strict_compilation_rejects_approximated_semantics(monkeypatch: pytest.MonkeyPatch) -> None:
    from agent_profile_compiler import compiler as compiler_module
    from agent_profile_compiler.model import CompilationResult, CompatibilityReport

    package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)

    def approximate_adapter(package, binding):
        report = CompatibilityReport(target="approximate-target", source_entry=package.entry_name)
        report.add(package.entry_name, "instructions", "approximated", "Prompt authority differs.")
        return CompilationResult(files={"agent.txt": "approximate\n"}, report=report)

    monkeypatch.setitem(compiler_module._TARGETS, "approximate-target", approximate_adapter)

    with pytest.raises(CompilationError, match="approximated"):
        compile_package(package, "approximate-target", {}, strict=True)
