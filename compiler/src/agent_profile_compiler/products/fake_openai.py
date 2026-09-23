"""A scripted OpenAI chat completions server for products with OpenAI compatible providers.

Implements `POST /v1/chat/completions` (streaming and non streaming) and
`GET /v1/models`. A director callable receives each parsed request and returns
the assistant reply: text and tool calls. Every request is appended to a JSON
Lines log so the probe can inspect what the model saw.
"""

from __future__ import annotations

import json
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

Director = Callable[[dict[str, Any]], dict[str, Any]]


def reply_text(value: str) -> dict[str, Any]:
    return {"content": value, "tool_calls": []}


def reply_tool_call(name: str, arguments: dict[str, Any], call_id: str | None = None) -> dict[str, Any]:
    return {
        "content": None,
        "tool_calls": [{"id": call_id or f"call_{uuid.uuid4().hex[:12]}", "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)}}],
    }


def system_text(request: dict[str, Any]) -> str:
    parts = []
    for message in request.get("messages", []):
        if message.get("role") in {"system", "developer"}:
            content = message.get("content")
            if isinstance(content, list):
                content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
            parts.append(str(content or ""))
    return "\n".join(parts)


def tool_names(request: dict[str, Any]) -> list[str]:
    names = []
    for tool in request.get("tools", []) or []:
        function = tool.get("function", {}) if isinstance(tool, dict) else {}
        if function.get("name"):
            names.append(function["name"])
    return names


def tool_results(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Every tool message in the conversation, with the tool name it answers."""

    calls: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    for message in request.get("messages", []):
        for call in message.get("tool_calls") or []:
            calls[call.get("id", "")] = call.get("function", {}).get("name", "?")
        if message.get("role") == "tool":
            content = message.get("content")
            if isinstance(content, list):
                content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
            results.append({"tool": calls.get(message.get("tool_call_id", ""), "?"), "content": content})
    return results


@dataclass
class FakeOpenAI:
    director: Director
    log_path: Path
    port: int = 0
    model: str = "probe-model"
    _server: ThreadingHTTPServer | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    @property
    def base_url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def requests(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def __enter__(self) -> "FakeOpenAI":
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:
                return

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                self._send_json(200, {"object": "list", "data": [{"id": server.model, "object": "model", "owned_by": "probe"}]})

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    request = json.loads(raw or b"{}")
                except json.JSONDecodeError:
                    request = {"raw": raw.decode("utf-8", "replace")}
                with open(server.log_path, "a", encoding="utf-8") as log:
                    log.write(json.dumps({"path": self.path, "request": request}) + "\n")
                if not urlparse(self.path).path.endswith("/chat/completions"):
                    self._send_json(404, {"error": {"message": f"unsupported path {self.path}"}})
                    return
                reply = server.director(request)
                finish = "tool_calls" if reply.get("tool_calls") else "stop"
                completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                model = request.get("model", server.model)
                if request.get("stream"):
                    self._stream(completion_id, model, reply, finish)
                else:
                    message: dict[str, Any] = {"role": "assistant", "content": reply.get("content")}
                    if reply.get("tool_calls"):
                        message["tool_calls"] = reply["tool_calls"]
                    self._send_json(200, {
                        "id": completion_id, "object": "chat.completion", "created": 0, "model": model,
                        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    })

            def _chunk(self, completion_id: str, model: str, delta: dict[str, Any], finish: str | None) -> None:
                payload = {"id": completion_id, "object": "chat.completion.chunk", "created": 0, "model": model,
                           "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
                self.wfile.write(f"data: {json.dumps(payload)}\n\n".encode("utf-8"))
                self.wfile.flush()

            def _stream(self, completion_id: str, model: str, reply: dict[str, Any], finish: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self._chunk(completion_id, model, {"role": "assistant", "content": ""}, None)
                if reply.get("content"):
                    self._chunk(completion_id, model, {"content": reply["content"]}, None)
                for index, call in enumerate(reply.get("tool_calls") or []):
                    self._chunk(completion_id, model, {"tool_calls": [{
                        "index": index, "id": call["id"], "type": "function",
                        "function": {"name": call["function"]["name"], "arguments": ""}}]}, None)
                    self._chunk(completion_id, model, {"tool_calls": [{
                        "index": index, "function": {"arguments": call["function"]["arguments"]}}]}, None)
                self._chunk(completion_id, model, {}, finish)
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
