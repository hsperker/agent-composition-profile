import asyncio
from pathlib import Path

from agent_framework import (
    Agent,
    BaseChatClient,
    ChatResponse,
    ChatResponseUpdate,
    Content,
    FunctionInvocationLayer,
    FunctionTool,
    MCPStreamableHTTPTool,
    Message,
    SkillsProvider,
    SkillsSourceContext,
)

from agent_profile_compiler.parser import load_package
from agent_profile_compiler.runtime import microsoft_agent_framework as adapter


ROOT = Path(__file__).parents[3]
EXAMPLE = ROOT / "examples" / "research-team"
DELEGATION = ROOT / "examples" / "runtime-probes" / "delegation"


class ScriptedChatClient(FunctionInvocationLayer, BaseChatClient):
    def __init__(self, responses: list[ChatResponse]):
        super().__init__()
        self.responses = responses
        self.seen_messages: list[list[Message]] = []
        self.seen_options: list[dict] = []

    def _inner_get_response(self, *, messages, stream, options, **kwargs):
        self.seen_messages.append(list(messages))
        self.seen_options.append(dict(options))
        response = self.responses.pop(0)
        if not stream:
            async def complete():
                return response

            return complete()

        async def updates():
            for message in response.messages:
                yield ChatResponseUpdate(role=message.role, contents=message.contents)

        return self._build_response_stream(updates())


def text_response(text: str) -> ChatResponse:
    return ChatResponse(messages=Message("assistant", [Content("text", text=text)]))


def function_response(name: str, task: str) -> ChatResponse:
    return ChatResponse(
        messages=Message(
            "assistant",
            [Content("function_call", name=name, arguments={"task": task}, call_id="call-1")],
        )
    )


def binding(clients: dict) -> dict:
    return {
        "capabilities": {"reasoning": True, "tool-use": True, "vision-input": False},
        "models": clients,
    }


def status(artifact, agent: str, feature: str) -> str:
    return next(f.status for f in artifact.report.findings if f.agent == agent and f.feature == feature)


def test_builds_native_microsoft_agents_skills_mcp_and_agent_tools() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    clients = {
        name: ScriptedChatClient([text_response(f"unused-{name}")])
        for name in package.agents
    }

    artifact = adapter.build(package, binding(clients), strict=False)

    assert all(isinstance(agent, Agent) for agent in artifact.native_agents.values())
    lead = artifact.native_agents["lead-researcher"]
    assert lead.name == "lead-researcher"
    assert lead.description == package.entry.description
    assert lead.default_options["instructions"] == package.entry.instructions
    assert isinstance(lead.context_providers[0], SkillsProvider)
    skills = asyncio.run(
        lead.context_providers[0]._source.get_skills(SkillsSourceContext(lead))
    )
    assert [skill.frontmatter.name for skill in skills] == [
        "source-evaluation",
        "query-planning",
    ]
    discovery = lead.context_providers[0]._create_instructions(None, skills)
    assert "source-evaluation" in discovery
    assert "Prefer primary sources" not in discovery
    activated = asyncio.run(
        lead.context_providers[0]._load_skill(skills, "source-evaluation")
    )
    assert "Prefer primary sources" in activated
    assert isinstance(lead.mcp_tools[0], MCPStreamableHTTPTool)
    assert {tool.name for tool in lead.default_options["tools"] if isinstance(tool, FunctionTool)} == {
        "explorer",
        "critic",
    }
    assert status(artifact, "lead-researcher", "name") == "preserved"
    assert status(artifact, "lead-researcher", "description") == "preserved"
    assert status(artifact, "lead-researcher", "instructions") == "preserved"
    assert status(artifact, "lead-researcher", "skills") == "preserved"
    assert status(artifact, "lead-researcher", "skills.durability") == "unverified"
    assert status(artifact, "lead-researcher", "plugins") == "resolved"
    assert status(artifact, "lead-researcher", "delegates") == "preserved"


def test_microsoft_runtime_executes_native_agent_as_tool_with_isolated_session() -> None:
    package = load_package(DELEGATION / "lead.agent.md", DELEGATION)
    worker_client = ScriptedChatClient([text_response("worker result")])
    coordinator_client = ScriptedChatClient(
        [
            function_response("worker", "Analyze this."),
            text_response("coordinator used worker result"),
        ]
    )
    artifact = adapter.build(
        package,
        binding({"coordinator": coordinator_client, "worker": worker_client}),
        strict=True,
    )

    result = adapter.run(artifact, "Solve the problem.")

    assert result.output == "coordinator used worker result"
    assert len(worker_client.seen_messages) == 1
    assert worker_client.seen_options[0]["instructions"] == package.agents["worker"].instructions
    assert [event.kind for event in result.observations] == [
        "delegate-started",
        "delegate-returned",
        "runtime-output",
    ]


def test_strict_microsoft_adapter_accepts_the_full_fixture_with_durability_unverified() -> None:
    package = load_package(EXAMPLE / "lead.agent.md", EXAMPLE)
    clients = {
        name: ScriptedChatClient([text_response(f"unused-{name}")])
        for name in package.agents
    }

    artifact = adapter.build(package, binding(clients), strict=True)

    assert not artifact.report.has_blocking_loss
    assert artifact.report.has_unverified
    modules = artifact.report.module_outcomes()
    assert modules["skills"]["outcome"] == "accepted"
    assert modules["skills"]["unverified"] == [
        "lead-researcher:skills.durability",
        "explorer:skills.durability",
    ]
