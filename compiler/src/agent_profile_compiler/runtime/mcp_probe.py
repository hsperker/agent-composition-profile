"""Support for the Agent Plugin activation probe.

The probe fixture under examples/runtime-probes/plugin-activation declares one
plugin with two deterministic echo servers: a stdio server the framework spawns
itself, and a streamable HTTP server this module starts as a subprocess. Both
report whether the client honored Agent Plugins §9 (environment and working
directory) and, for HTTP, whether the configured header arrived.
"""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

HTTP_PORT = 8765
ECHO_TASK = "probe"


def echo_tool_names(names: Iterable[str]) -> list[str]:
    """The framework-visible names of the probe's echo tools, in stable order."""

    return sorted(name for name in names if "echo" in name)


_ECHO_PAYLOAD = re.compile(r'\{[^{}]*"cwd"[^{}]*\}')


def parse_echo_result(text: Any) -> dict[str, Any]:
    """Decode an echo payload from however a framework wraps tool results.

    Frameworks stringify MCP results differently: bare text, a JSON object with
    a `result` field, or the repr of a CallToolResult. The echo payload is the
    innermost brace-delimited object carrying the `cwd` key; escaped quotes
    from nested JSON strings are unescaped first.
    """

    if isinstance(text, dict) and "cwd" in text:
        return text
    raw = str(text).replace('\\"', '"')
    match = _ECHO_PAYLOAD.search(raw)
    if match is None:
        return {"raw": raw}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"raw": raw}


def wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            socket.create_connection((host, port), timeout=0.2).close()
            return
        except OSError:
            time.sleep(0.1)
    raise TimeoutError(f"echo HTTP server did not listen on {host}:{port} within {timeout}s")


@contextmanager
def echo_http_server(plugin_root: Path, port: int = HTTP_PORT) -> Iterator[subprocess.Popen]:
    """Run the fixture's echo server over streamable HTTP for the duration of a probe."""

    script = plugin_root / "servers" / "echo_server.py"
    process = subprocess.Popen(
        [sys.executable, str(script), "--transport", "streamable-http", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_port("127.0.0.1", port)
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
