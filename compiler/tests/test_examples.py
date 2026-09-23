"""The packages under compiler/examples must compile strictly for every executed product target."""

from pathlib import Path

import pytest
import yaml

from agent_profile_compiler.compiler import compile_package
from agent_profile_compiler.parser import load_package

EXAMPLES = Path(__file__).parents[1] / "examples"
BINDINGS = yaml.safe_load((EXAMPLES / "bindings.yaml").read_text(encoding="utf-8"))["targets"]
PACKAGES = {
    "minimal": "researcher.agent.md",
    "skills-and-plugin": "researcher.agent.md",
    "subagents": "lead.agent.md",
}


@pytest.mark.parametrize("target", sorted(BINDINGS))
@pytest.mark.parametrize("package_name", sorted(PACKAGES))
def test_examples_compile_strictly_for_every_product_target(package_name: str, target: str) -> None:
    root = EXAMPLES / package_name
    package = load_package(root / PACKAGES[package_name], root)

    result = compile_package(package, target, BINDINGS[target], strict=True)

    assert not result.report.has_blocking_loss
    assert "compatibility-report.json" in result.files
    assert any(path != "compatibility-report.json" for path in result.files)


def test_subagents_example_emits_every_agent() -> None:
    root = EXAMPLES / "subagents"
    package = load_package(root / "lead.agent.md", root)

    result = compile_package(package, "claude-code", BINDINGS["claude-code"], strict=True)

    assert {".claude/agents/lead.md", ".claude/agents/explorer.md", ".claude/agents/critic.md"} <= set(result.files)
    assert "Agent(explorer, critic)" in result.files[".claude/agents/lead.md"]
