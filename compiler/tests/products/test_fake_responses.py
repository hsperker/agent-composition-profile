import json
from pathlib import Path

import pytest

from agent_profile_compiler.products.fake_responses import (
    FakeResponses,
    instructions_text,
    reply_function_call,
    reply_text,
    tool_names,
    tool_results,
)

openai = pytest.importorskip("openai")


def test_scripted_responses_server_round_trips_with_the_openai_sdk(tmp_path: Path) -> None:
    def director(request):
        if not tool_results(request):
            return reply_function_call("echo", {"text": "probe"}, call_id="call_1")
        return reply_text("final: " + tool_results(request)[0]["content"])

    tools = [{"type": "function", "name": "echo", "description": "echo",
              "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}]
    with FakeResponses(director, tmp_path / "log.jsonl") as fake:
        client = openai.OpenAI(base_url=fake.base_url, api_key="probe")
        calls = []
        with client.responses.stream(model="probe-model", instructions="SYS", input=[{"role": "user", "content": "go"}], tools=tools) as stream:
            for event in stream:
                if event.type == "response.output_item.done" and event.item.type == "function_call":
                    calls.append(event.item)
            assert stream.get_final_response().status == "completed"
        assert [(c.name, json.loads(c.arguments), c.call_id) for c in calls] == [("echo", {"text": "probe"}, "call_1")]
        second = client.responses.create(model="probe-model", instructions="SYS", tools=tools, input=[
            {"role": "user", "content": "go"},
            {"type": "function_call", "call_id": "call_1", "name": "echo", "arguments": json.dumps({"text": "probe"})},
            {"type": "function_call_output", "call_id": "call_1", "output": "echoed"},
        ])
        assert second.output_text == "final: echoed"
        requests = [item["request"] for item in fake.requests()]
        assert instructions_text(requests[0]) == "SYS" and tool_names(requests[0]) == ["echo"]


def test_namespaced_function_calls_carry_the_namespace_on_the_output_item(tmp_path: Path) -> None:
    from agent_profile_compiler.products.fake_responses import tool_namespace

    tools = [{"type": "namespace", "name": "multi_agent_v1", "tools": [
        {"type": "function", "name": "spawn_agent", "parameters": {"type": "object", "properties": {}}}]}]
    request = {"tools": tools}
    assert tool_names(request) == ["spawn_agent"]
    assert tool_namespace(request, "spawn_agent") == "multi_agent_v1"
    assert tool_namespace(request, "exec_command") is None

    def director(request):
        return reply_function_call("spawn_agent", {"message": "go"}, call_id="call_1", namespace=tool_namespace(request, "spawn_agent"))

    with FakeResponses(director, tmp_path / "log.jsonl") as fake:
        client = openai.OpenAI(base_url=fake.base_url, api_key="probe")
        response = client.responses.create(model="probe-model", input="go", tools=tools)
    item = response.output[0].model_dump()
    assert item["name"] == "spawn_agent"
    assert item["namespace"] == "multi_agent_v1"
