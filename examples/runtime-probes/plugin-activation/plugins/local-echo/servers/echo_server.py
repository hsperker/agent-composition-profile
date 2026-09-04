"""Deterministic MCP echo server for Agent Plugin activation probes.

Runs under the MCP Python SDK 1.x (FastMCP) and 2.x (MCPServer). One tool is
exposed, named after the transport so two servers never collide:

    echo_stdio(text) / echo_http(text) -> JSON string

The result reports the text, the PROBE_LABEL environment value, whether the
Agent Plugins PLUGIN_ROOT and PLUGIN_DATA variables were provided, and the
working directory, so a client's env/cwd handling is observable.

The streamable HTTP transport requires the header X-Probe-Token: probe-token
and answers 401 otherwise, so header handling is observable too.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REQUIRED_HEADER = "x-probe-token"
REQUIRED_TOKEN = "probe-token"


def build_server(transport: str):
    try:
        from mcp.server.fastmcp import FastMCP as ServerClass  # MCP SDK 1.x
    except ModuleNotFoundError:
        from mcp.server.mcpserver import MCPServer as ServerClass  # MCP SDK 2.x
    try:
        server = ServerClass("acp-echo", stateless_http=True)
    except TypeError:
        server = ServerClass("acp-echo")
    label = "stdio" if transport == "stdio" else "http"

    def echo(text: str) -> str:
        """Echo the text back with probe diagnostics."""
        return json.dumps(
            {
                "text": text,
                "label": os.environ.get("PROBE_LABEL", label),
                "plugin_root_env": "PLUGIN_ROOT" in os.environ,
                "plugin_data_env": "PLUGIN_DATA" in os.environ,
                "cwd": os.getcwd(),
            },
            sort_keys=True,
        )

    server.tool(name=f"echo_{label}", description=f"Echo text back over {label}.")(echo)
    return server


def run_http(server, host: str, port: int) -> None:
    import uvicorn
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class RequireToken(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.headers.get(REQUIRED_HEADER) != REQUIRED_TOKEN:
                return JSONResponse({"error": "missing or wrong X-Probe-Token"}, status_code=401)
            return await call_next(request)

    app = server.streamable_http_app()
    app.add_middleware(RequireToken)
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = build_server(args.transport)
    if args.transport == "stdio":
        server.run(transport="stdio")
    else:
        run_http(server, args.host, args.port)


if __name__ == "__main__":
    sys.exit(main())
