from dataclasses import dataclass, field
from pathlib import Path

import pytest
from agno.agent import Agent
from agno.models.base import Model
from agno.models.response import ModelResponse
from agno.team import Team
from agno.tools.mcp import MCPTools

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import agno as adapter
from agent_profile_compiler.runtime.common import RuntimeCompatibilityError


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"


@dataclass
class FixedAgnoModel(Model):
    response_text: str = "deterministic Agno result"
    seen_calls: list = field(default_factory=list)

    def invoke(self, *args, **kwargs):
        self.seen_calls.append((args, kwargs))
        return ModelResponse(role="assistant", content=self.response_text)

    async def ainvoke(self, *args, **kwargs):
        return self.invoke(*args, **kwargs)

    def invoke_stream(self, *args, **kwargs):
        yield self.invoke(*args, **kwargs)

    async def ainvoke_stream(self, *args, **kwargs):
        yield self.invoke(*args, **kwargs)

    def _parse_provider_response(self, response, **kwargs):
        return response

    def _parse_provider_response_delta(self, response):
        return response


def binding() -> dict:
    return {
        "capabilities": {"reasoning": True, "tool-use": True, "vision-input": False},
        "models": {
            name: FixedAgnoModel(id=f"fixed-{name}")
            for name in ("lead-researcher", "explorer", "critic")
        },
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(f.status for f in artifact.report.findings if f.agent == agent and f.feature == feature)


def test_builds_native_agno_agents_skills_mcp_and_team() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    artifact = adapter.build(package, binding(), strict=False)

    assert all(isinstance(agent, Agent) for agent in artifact.native_agents.values())
    team = artifact.metadata["teams"]["lead-researcher"]
    assert isinstance(team, Team)
    assert [member.name for member in team.members] == ["explorer", "critic"]
    lead = artifact.native_agents["lead-researcher"]
    assert lead.name == "lead-researcher"
    assert lead.description == package.entry.description
    assert lead.instructions == package.entry.instructions
    assert lead.skills.get_skill_names() == ["source-evaluation", "query-planning"]
    discovery = lead.skills.get_system_prompt_snippet()
    assert "source-evaluation" in discovery
    assert "Prefer primary sources" not in discovery
    activated = lead.skills._get_skill_instructions("source-evaluation")
    assert "Prefer primary sources" in activated
    assert isinstance(lead.tools[0], MCPTools)
    assert lead.tools[0].url == "https://research.example.com/mcp"
    assert status(artifact, "lead-researcher", "name") == "preserved"
    assert status(artifact, "lead-researcher", "description") == "approximated"
    assert status(artifact, "lead-researcher", "instructions") == "preserved"
    assert status(artifact, "lead-researcher", "skills") == "preserved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "plugins") == "resolved"
    assert status(artifact, "lead-researcher", "delegates") == "approximated"


def test_runs_real_agno_leaf_with_its_persistent_instructions() -> None:
    package = load_package(EXAMPLE / "agents" / "critic.agent.md", EXAMPLE)
    artifact = adapter.build(package, binding(), strict=False)

    result = adapter.run(artifact, "Challenge this.")

    assert result.output == "deterministic Agno result"
    assert artifact.native_agents["critic"].model.seen_calls
    assert result.observations[-1].kind == "runtime-output"


def test_strict_agno_rejects_description_and_team_semantic_changes() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)

    with pytest.raises(RuntimeCompatibilityError, match="description.*delegates"):
        adapter.build(package, binding(), strict=True)
