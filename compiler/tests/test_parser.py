from pathlib import Path
import textwrap

import pytest

from agent_profile_compiler.model import ProfileError
from agent_profile_compiler.parser import load_package


ROOT = Path(__file__).parents[2]
EXAMPLE = ROOT / "examples" / "research-team"


def write_agent(path: Path, frontmatter: str, body: str = "# Instructions\n\nDo the work.\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{textwrap.dedent(frontmatter).strip()}\n---\n\n{body}", encoding="utf-8")


def test_loads_research_team_and_discovers_standard_components() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    assert package.entry_name == "lead-researcher"
    assert set(package.agents) == {"lead-researcher", "explorer", "critic"}
    lead = package.agents["lead-researcher"]
    assert lead.description == lead.description.strip()
    assert lead.requires == frozenset({"reasoning", "tool-use"})
    assert lead.prefers == frozenset({"vision-input"})
    assert [skill.name for skill in lead.direct_skills] == ["source-evaluation"]
    assert [plugin.name for plugin in lead.plugins] == ["web-research"]
    assert [skill.name for skill in lead.plugins[0].skills] == ["query-planning"]
    assert [server.name for server in lead.plugins[0].mcp_servers] == ["research"]
    assert lead.delegate_names == ("explorer", "critic")


@pytest.mark.parametrize("field", ["spec: portable-agent/0.1", "extensions: {}", "metadata: {}", "license: MIT"])
def test_rejects_fields_outside_the_small_core(tmp_path: Path, field: str) -> None:
    write_agent(tmp_path / "agent.md", f"""
        name: test-agent
        description: Tests the closed schema.
        {field}
    """)

    with pytest.raises(ProfileError, match="unknown top-level field"):
        load_package(tmp_path / "agent.md", tmp_path)


def test_rejects_yaml_aliases(tmp_path: Path) -> None:
    write_agent(tmp_path / "agent.md", """
        name: test-agent
        description: &description Tests aliases.
        model:
          requires: *description
    """)

    with pytest.raises(ProfileError, match="anchors and aliases"):
        load_package(tmp_path / "agent.md", tmp_path)


def test_rejects_empty_markdown_body(tmp_path: Path) -> None:
    write_agent(tmp_path / "agent.md", """
        name: test-agent
        description: Tests empty bodies.
    """, body=" \n\t\n")

    with pytest.raises(ProfileError, match="instruction body"):
        load_package(tmp_path / "agent.md", tmp_path)


def test_rejects_delegate_cycles(tmp_path: Path) -> None:
    write_agent(tmp_path / "a.agent.md", """
        name: agent-a
        description: Delegates to B.
        delegates: [./b.agent.md]
    """)
    write_agent(tmp_path / "b.agent.md", """
        name: agent-b
        description: Delegates to A.
        delegates: [./a.agent.md]
    """)

    with pytest.raises(ProfileError, match="delegate cycle"):
        load_package(tmp_path / "a.agent.md", tmp_path)


def test_rejects_duplicate_direct_delegate_names(tmp_path: Path) -> None:
    write_agent(tmp_path / "root.agent.md", """
        name: root-agent
        description: Has ambiguous delegates.
        delegates: [./a.agent.md, ./b.agent.md]
    """)
    write_agent(tmp_path / "a.agent.md", """
        name: worker
        description: First worker.
    """)
    write_agent(tmp_path / "b.agent.md", """
        name: worker
        description: Second worker.
    """)

    with pytest.raises(ProfileError, match="duplicate direct delegate name"):
        load_package(tmp_path / "root.agent.md", tmp_path)



def test_rejects_duplicate_agent_names_anywhere_in_reachable_package(tmp_path: Path) -> None:
    write_agent(tmp_path / "root.agent.md", """
        name: root-agent
        description: Reaches two branches.
        delegates: [./left.agent.md, ./right.agent.md]
    """)
    write_agent(tmp_path / "left.agent.md", """
        name: left-agent
        description: Reaches the first worker.
        delegates: [./left/worker.agent.md]
    """)
    write_agent(tmp_path / "right.agent.md", """
        name: right-agent
        description: Reaches the second worker.
        delegates: [./right/worker.agent.md]
    """)
    write_agent(tmp_path / "left" / "worker.agent.md", """
        name: worker
        description: First globally named worker.
    """)
    write_agent(tmp_path / "right" / "worker.agent.md", """
        name: worker
        description: Second globally named worker.
    """)

    with pytest.raises(ProfileError, match="duplicate package agent name"):
        load_package(tmp_path / "root.agent.md", tmp_path)

def test_rejects_reference_that_escapes_package_root(tmp_path: Path) -> None:
    package = tmp_path / "package"
    outside = tmp_path / "outside"
    outside.mkdir()
    write_agent(package / "agent.md", """
        name: test-agent
        description: References an outside skill.
        skills: [../outside]
    """)
    (outside / "SKILL.md").write_text("---\nname: outside\ndescription: Outside.\n---\nBody\n", encoding="utf-8")

    with pytest.raises(ProfileError, match="outside package root"):
        load_package(package / "agent.md", package)


def write_skill(root: Path, *, name: str, description: str = "A test skill.") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# Instructions\n\nUse the skill.\n",
        encoding="utf-8",
    )


def write_plugin(root: Path, *, name: str, mcp_servers: dict | None = None) -> None:
    import json

    root.mkdir(parents=True, exist_ok=True)
    (root / "plugin.json").write_text(
        json.dumps(
            {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "name": name,
            }
        ),
        encoding="utf-8",
    )
    if mcp_servers is not None:
        (root / "mcp.json").write_text(
            json.dumps(
                {
                    "$schema": "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                    "mcpServers": mcp_servers,
                }
            ),
            encoding="utf-8",
        )


def test_accepts_agent_plugin_names_allowed_by_agent_plugins_schema(tmp_path: Path) -> None:
    plugin = tmp_path / "plugins" / "vendor-plugin"
    write_plugin(
        plugin,
        name="example.org-research",
        mcp_servers={"openaiDeveloperDocs": {"type": "streamable-http", "url": "https://example.test/mcp"}},
    )
    write_agent(tmp_path / "agent.md", """
        name: test-agent
        description: Uses a standards-compliant plugin name and MCP server key.
        plugins: [./plugins/vendor-plugin]
    """)

    package = load_package(tmp_path / "agent.md", tmp_path)

    assert package.entry.plugins[0].name == "example.org-research"
    assert package.entry.plugins[0].mcp_servers[0].name == "openaiDeveloperDocs"


def test_rejects_agent_skill_name_that_does_not_match_directory(tmp_path: Path) -> None:
    write_skill(tmp_path / "skills" / "actual-directory", name="different-name")
    write_agent(tmp_path / "agent.md", """
        name: test-agent
        description: References a mismatched Agent Skill directory.
        skills: [./skills/actual-directory]
    """)

    with pytest.raises(ProfileError, match="must match its parent directory"):
        load_package(tmp_path / "agent.md", tmp_path)


def test_rejects_agent_plugin_mcp_fields_outside_the_1_0_schema(tmp_path: Path) -> None:
    plugin = tmp_path / "plugins" / "invalid-plugin"
    write_plugin(
        plugin,
        name="invalid-plugin",
        mcp_servers={
            "research": {
                "type": "streamable-http",
                "url": "https://example.test/mcp",
                "unexpected": True,
            }
        },
    )
    write_agent(tmp_path / "agent.md", """
        name: test-agent
        description: References an invalid Agent Plugin MCP server.
        plugins: [./plugins/invalid-plugin]
    """)

    with pytest.raises(ProfileError, match="does not conform to Agent Plugins 1.0.0 MCP schema"):
        load_package(tmp_path / "agent.md", tmp_path)
