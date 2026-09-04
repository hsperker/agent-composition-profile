from pathlib import Path

import pytest

from agent_profile_compiler.model import Agent, McpServer, Plugin, Skill
from agent_profile_compiler.runtime.plugins import PluginCatalog
from agent_profile_compiler.runtime.skills import SkillCatalog


def skill(name: str, instructions: str) -> Skill:
    return Skill(
        root=Path("skills") / name,
        name=name,
        description=f"Use {name} when evidence needs checking.",
        instructions=instructions,
    )


def test_skill_catalog_discloses_metadata_before_instructions() -> None:
    catalog = SkillCatalog("explorer", [skill("source-evaluation", "SECRET BODY")])

    assert catalog.metadata() == [
        {
            "name": "source-evaluation",
            "description": "Use source-evaluation when evidence needs checking.",
        }
    ]
    assert "SECRET BODY" not in catalog.discovery_text()
    assert catalog.activated_names == ()

    assert catalog.activate("source-evaluation") == "SECRET BODY"
    assert catalog.activated_names == ("source-evaluation",)


def test_skill_activation_is_agent_private() -> None:
    shared = skill("source-evaluation", "PRIVATE INSTRUCTIONS")
    explorer = SkillCatalog("explorer", [shared])
    lead = SkillCatalog("lead-researcher", [shared])

    explorer.activate("source-evaluation")

    assert explorer.activated_names == ("source-evaluation",)
    assert lead.activated_names == ()


def test_unknown_skill_fails_explicitly() -> None:
    catalog = SkillCatalog("critic", [])

    with pytest.raises(KeyError, match="critic.*missing-skill"):
        catalog.activate("missing-skill")


def test_plugin_catalog_preserves_server_config_and_agent_ownership() -> None:
    plugin = Plugin(
        root=Path("plugins/web-research"),
        name="web-research",
        mcp_servers=(
            McpServer(
                name="research",
                config={
                    "type": "streamable-http",
                    "url": "https://research.example.com/mcp",
                    "headers": {"X-Mode": "primary"},
                },
            ),
        ),
    )
    agent = Agent(
        source_path=Path("explorer.agent.md"),
        relative_path=Path("explorer.agent.md"),
        name="explorer",
        description="Explores sources.",
        instructions="Research.",
        plugins=(plugin,),
    )

    catalog = PluginCatalog.from_agent(agent)

    assert catalog.owner == "explorer"
    assert catalog.server("research").config == {
        "type": "streamable-http",
        "url": "https://research.example.com/mcp",
        "headers": {"X-Mode": "primary"},
    }
    with pytest.raises(KeyError, match="explorer.*missing"):
        catalog.server("missing")
