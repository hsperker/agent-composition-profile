from pathlib import Path

import pytest
from crewai import Agent as CrewAgent
from crewai import Crew
from crewai.llms.base_llm import BaseLLM
from crewai.skills.tool import create_skill_loader_tool

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import crewai as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"


class FixedCrewLLM(BaseLLM):
    response: str = "Final Answer: deterministic result"
    seen_messages: list = []

    def call(self, messages, tools=None, callbacks=None, available_functions=None, **kwargs):
        self.seen_messages.append(messages)
        return self.response


def binding() -> dict:
    return {
        "capabilities": {
            "reasoning": True,
            "tool-use": True,
            "vision-input": False,
        },
        "models": {
            name: FixedCrewLLM(model=f"deterministic-{name}")
            for name in ("lead-researcher", "explorer", "critic")
        },
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(
        finding.status
        for finding in artifact.report.findings
        if finding.agent == agent and finding.feature == feature
    )


def test_builds_native_crewai_agents_skills_mcp_and_crew_relationship() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    artifact = adapter.build(package, binding(), strict=False)

    assert all(isinstance(agent, CrewAgent) for agent in artifact.native_agents.values())
    assert isinstance(artifact.metadata["crew"], Crew)
    lead = artifact.native_agents["lead-researcher"]
    assert lead.role == "lead-researcher"
    assert lead.goal == package.entry.description
    assert lead.backstory == package.entry.instructions
    assert [skill.frontmatter.name for skill in lead.skills] == [
        "source-evaluation",
        "query-planning",
    ]
    assert all(skill.instructions is None for skill in lead.skills)
    loader = create_skill_loader_tool(lead.skills, source=lead)
    assert loader is not None
    loaded = loader._run("source-evaluation")
    assert "Prefer primary sources" in loaded
    assert lead.mcps[0].url == "https://research.example.com/mcp"
    assert lead.allow_delegation is True
    assert status(artifact, "lead-researcher", "name") == "approximated"
    assert status(artifact, "lead-researcher", "description") == "approximated"
    assert status(artifact, "lead-researcher", "instructions") == "approximated"
    assert status(artifact, "lead-researcher", "skills") == "preserved"
    assert status(artifact, "lead-researcher", "plugins") == "resolved"
    assert status(artifact, "lead-researcher", "delegates") == "approximated"


def test_runs_a_real_crewai_leaf_agent_with_its_own_prompt() -> None:
    package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)
    only_critic = binding()
    artifact = adapter.build(package, only_critic, strict=False)

    result = adapter.run(artifact, "Challenge this conclusion.")

    assert "deterministic result" in result.output
    messages = only_critic["models"]["critic"].seen_messages
    assert messages
    system_content = next(
        message["content"] for message in messages[0] if message["role"] == "system"
    )
    assert package.entry.instructions.strip() in system_content
    assert result.observations[-1].kind == "runtime-output"


def test_strict_crewai_rejects_role_prompt_and_team_semantic_changes() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    with pytest.raises(RuntimeCompatibilityError, match="name.*description.*instructions.*delegates"):
        adapter.build(package, binding(), strict=True)
