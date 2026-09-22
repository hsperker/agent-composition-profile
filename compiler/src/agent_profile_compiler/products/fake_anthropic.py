"""A scripted Anthropic Messages API server for Claude Code probes.

Implements enough of `POST /v1/messages` (streaming and non streaming) and
`POST /v1/messages/count_tokens` for Claude Code to run headless. A director
callable receives each parsed request and returns the assistant content
blocks to send back: text blocks and tool_use blocks. Every request is
appended to a JSON Lines log so the probe can inspect the conversation.
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

Director = Callable[[dict[str, Any]], list[dict[str, Any]]]


def text(value: str) -> dict[str, Any]:
    return {"type": "text", "text": value}


def tool_use(name: str, arguments: dict[str, Any], call_id: str | None = None) -> dict[str, Any]:
    return {"type": "tool_use", "id": call_id or f"toolu_{uuid.uuid4().hex[:12]}", "name": name, "input": arguments}


def system_text(request: dict[str, Any]) -> str:
    """The request's system prompt as one string, whatever shape it arrived in."""

    system = request.get("system", "")
    if isinstance(system, str):
        return system
    return "\n".join(block.get("text", "") for block in system if isinstance(block, dict))


def tool_names(request: dict[str, Any]) -> list[str]:
    return [tool.get("name", "") for tool in request.get("tools", []) if isinstance(tool, dict)]


def tool_results(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Every tool_result block in the conversation, with the tool name it answers."""

    calls: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    for message in request.get("messages", []):
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "tool_use":
                calls[block["id"]] = block["name"]
            if block.get("type") == "tool_result":
                inner = block.get("content")
                if isinstance(inner, list):
                    inner = "".join(item.get("text", "") for item in inner if isinstance(item, dict))
                results.append({"tool": calls.get(block.get("tool_use_id"), "?"), "content": inner})
    return results


@dataclass
class FakeAnthropic:
    director: Director
    log_path: Path
    port: int = 0
    model: str = "claude-probe"
    _server: ThreadingHTTPServer | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    @property
    def base_url(self) -> str:
        assert self._server is not None
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def requests(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def __enter__(self) -> "FakeAnthropic":
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args: Any) -> None:  # keep the probe output quiet
                return

            def _read_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    return json.loads(raw or b"{}")
                except json.JSONDecodeError:
                    return {"raw": raw.decode("utf-8", "replace")}

            def _send_json(self, status: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:
                self._send_json(200, {"data": [], "has_more": False})

            def do_POST(self) -> None:
                request = self._read_json()
                with open(server.log_path, "a", encoding="utf-8") as log:
                    log.write(json.dumps({"path": self.path, "request": request}) + "\n")
                path = urlparse(self.path).path
                if path.endswith("/count_tokens"):
                    self._send_json(200, {"input_tokens": 1})
                    return
                if not path.endswith("/messages"):
                    self._send_json(200, {})
                    return
                blocks = server.director(request)
                stop_reason = "tool_use" if any(b["type"] == "tool_use" for b in blocks) else "end_turn"
                message_id = f"msg_{uuid.uuid4().hex[:12]}"
                if request.get("stream"):
                    self._stream(message_id, blocks, stop_reason, request.get("model", server.model))
                else:
                    self._send_json(200, {
                        "id": message_id, "type": "message", "role": "assistant",
                        "model": request.get("model", server.model), "content": blocks,
                        "stop_reason": stop_reason, "stop_sequence": None,
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    })

            def _event(self, name: str, payload: dict[str, Any]) -> None:
                data = json.dumps({"type": name, **payload})
                self.wfile.write(f"event: {name}\ndata: {data}\n\n".encode("utf-8"))
                self.wfile.flush()

            def _stream(self, message_id: str, blocks: list[dict[str, Any]], stop_reason: str, model: str) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self._event("message_start", {"message": {
                    "id": message_id, "type": "message", "role": "assistant", "model": model,
                    "content": [], "stop_reason": None, "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 0},
                }})
                for index, block in enumerate(blocks):
                    if block["type"] == "text":
                        self._event("content_block_start", {"index": index, "content_block": {"type": "text", "text": ""}})
                        self._event("content_block_delta", {"index": index, "delta": {"type": "text_delta", "text": block["text"]}})
                    else:
                        self._event("content_block_start", {"index": index, "content_block": {
                            "type": "tool_use", "id": block["id"], "name": block["name"], "input": {}}})
                        self._event("content_block_delta", {"index": index, "delta": {
                            "type": "input_json_delta", "partial_json": json.dumps(block["input"])}})
                    self._event("content_block_stop", {"index": index})
                self._event("message_delta", {"delta": {"stop_reason": stop_reason, "stop_sequence": None},
                                              "usage": {"output_tokens": 1}})
                self._event("message_stop", {})

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
