"""A scripted OpenAI Responses API server for Codex probes.

Codex talks to its provider only through the Responses API. This server
implements `POST /v1/responses` for streaming (server sent events) and non
streaming requests, plus `GET /v1/models`. A director callable receives each
parsed request and returns the assistant output: text and function calls.
Every request is appended to a JSON Lines log so the probe can inspect what
the model saw: instructions, input items, and tools. Standard library only.
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
    return {"text": value, "calls": []}


def reply_function_call(name: str, arguments: dict[str, Any], call_id: str | None = None, namespace: str | None = None) -> dict[str, Any]:
    """A function call; `namespace` names the namespace tool the function belongs to, if any."""

    call = {"name": name, "arguments": json.dumps(arguments), "call_id": call_id or f"call_{uuid.uuid4().hex[:12]}"}
    if namespace:
        call["namespace"] = namespace
    return {"text": None, "calls": [call]}


def namespaced_tools(request: dict[str, Any]) -> dict[str, str]:
    """Function name to namespace, for every function offered inside a namespace tool."""

    found: dict[str, str] = {}
    for tool in request.get("tools", []) or []:
        if isinstance(tool, dict) and tool.get("type") == "namespace":
            for fn in tool.get("tools", []):
                if isinstance(fn, dict) and fn.get("name"):
                    found[fn["name"]] = tool.get("name", "")
    return found


def tool_namespace(request: dict[str, Any], name: str) -> str | None:
    """The namespace tool that offers function `name`, or None for a top level function."""

    return namespaced_tools(request).get(name)


def instructions_text(request: dict[str, Any]) -> str:
    """Instructions plus any system or developer input messages, as one string."""

    parts = [str(request.get("instructions") or "")]
    for item in request.get("input", []) or []:
        if isinstance(item, dict) and item.get("role") in {"system", "developer"}:
            parts.append(_content_text(item.get("content")))
    return "\n".join(part for part in parts if part)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(str(block.get("text", "")) for block in content if isinstance(block, dict))
    return str(content or "")


def tool_names(request: dict[str, Any]) -> list[str]:
    """Function tool names, flattening Codex's namespace tools; other types appear as <type>."""

    names = []
    for tool in request.get("tools", []) or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") == "function" and tool.get("name"):
            names.append(tool["name"])
        elif tool.get("type") == "namespace":
            names.extend(fn.get("name", "") for fn in tool.get("tools", []) if isinstance(fn, dict) and fn.get("name"))
        elif tool.get("type") not in (None, "function"):
            names.append(f"<{tool['type']}>")
    return names


def context_text(request: dict[str, Any]) -> str:
    """Everything the model sees besides the final user turn: instructions and earlier input messages."""

    parts = [str(request.get("instructions") or "")]
    items = [item for item in request.get("input", []) or [] if isinstance(item, dict)]
    for item in items[:-1]:
        if item.get("type") in (None, "message"):
            parts.append(_content_text(item.get("content")))
    return "\n".join(part for part in parts if part)


def tool_results(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Every function_call_output item, with the tool name it answers."""

    calls: dict[str, str] = {}
    results: list[dict[str, Any]] = []
    for item in request.get("input", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            calls[item.get("call_id", "")] = item.get("name", "?")
        if item.get("type") == "function_call_output":
            results.append({"tool": calls.get(item.get("call_id", ""), "?"), "content": _content_text(item.get("output"))})
    return results


@dataclass
class FakeResponses:
    director: Director
    log_path: Path
    port: int = 0
    model: str = "probe-model"
    host: str = "127.0.0.1"
    _server: ThreadingHTTPServer | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    @property
    def base_url(self) -> str:
        assert self._server is not None
        return f"http://{self.host}:{self._server.server_address[1]}/v1"

    def requests(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        return [json.loads(line) for line in self.log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def __enter__(self) -> "FakeResponses":
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", encoding="utf-8")
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

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
                if not urlparse(self.path).path.endswith("/responses"):
                    self._send_json(404, {"error": {"message": f"unsupported path {self.path}"}})
                    return
                reply = server.director(request)
                response_id = f"resp_{uuid.uuid4().hex[:12]}"
                output = _output_items(reply)
                completed = {
                    "id": response_id, "object": "response", "created_at": 0, "status": "completed",
                    "model": request.get("model", server.model), "output": output,
                    "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
                }
                if request.get("stream"):
                    self._stream(response_id, output, completed)
                else:
                    self._send_json(200, completed)

            def _event(self, name: str, payload: dict[str, Any]) -> None:
                data = json.dumps({"type": name, **payload})
                self.wfile.write(f"event: {name}\ndata: {data}\n\n".encode("utf-8"))
                self.wfile.flush()

            def _stream(self, response_id: str, output: list[dict[str, Any]], completed: dict[str, Any]) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                base = {"id": response_id, "object": "response", "created_at": 0, "model": completed["model"], "output": []}
                self._event("response.created", {"sequence_number": 0, "response": {**base, "status": "in_progress"}})
                self._event("response.in_progress", {"sequence_number": 1, "response": {**base, "status": "in_progress"}})
                seq = 2
                for index, item in enumerate(output):
                    if item["type"] == "message":
                        self._event("response.output_item.added", {"sequence_number": seq, "output_index": index,
                                                                    "item": {**item, "content": [], "status": "in_progress"}}); seq += 1
                        text = item["content"][0]["text"]
                        self._event("response.content_part.added", {"sequence_number": seq, "output_index": index, "item_id": item["id"],
                                                                     "content_index": 0, "part": {"type": "output_text", "text": "", "annotations": []}}); seq += 1
                        self._event("response.output_text.delta", {"sequence_number": seq, "output_index": index, "item_id": item["id"],
                                                                    "content_index": 0, "delta": text}); seq += 1
                        self._event("response.output_text.done", {"sequence_number": seq, "output_index": index, "item_id": item["id"],
                                                                   "content_index": 0, "text": text}); seq += 1
                        self._event("response.content_part.done", {"sequence_number": seq, "output_index": index, "item_id": item["id"],
                                                                    "content_index": 0, "part": item["content"][0]}); seq += 1
                    else:
                        self._event("response.output_item.added", {"sequence_number": seq, "output_index": index,
                                                                    "item": {**item, "arguments": "", "status": "in_progress"}}); seq += 1
                        self._event("response.function_call_arguments.delta", {"sequence_number": seq, "output_index": index,
                                                                                "item_id": item["id"], "delta": item["arguments"]}); seq += 1
                        self._event("response.function_call_arguments.done", {"sequence_number": seq, "output_index": index,
                                                                               "item_id": item["id"], "arguments": item["arguments"]}); seq += 1
                    self._event("response.output_item.done", {"sequence_number": seq, "output_index": index, "item": item}); seq += 1
                self._event("response.completed", {"sequence_number": seq, "response": completed})

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()


def _output_items(reply: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if reply.get("text"):
        items.append({"type": "message", "id": f"msg_{uuid.uuid4().hex[:12]}", "role": "assistant", "status": "completed",
                      "content": [{"type": "output_text", "text": reply["text"], "annotations": []}]})
    for call in reply.get("calls") or []:
        item = {"type": "function_call", "id": f"fc_{uuid.uuid4().hex[:12]}", "status": "completed",
                "call_id": call["call_id"], "name": call["name"], "arguments": call["arguments"]}
        if call.get("namespace"):
            item["namespace"] = call["namespace"]
        items.append(item)
    return items
