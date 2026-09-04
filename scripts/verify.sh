#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/compiler/src"
CACHE_DIR="${ACP_UV_CACHE_DIR:-/tmp/uv-cache-agent-composition-profile}"
UV=(uv run --python 3.13 --project "$ROOT/compiler" --extra test)

UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" pytest -q "$ROOT/compiler/tests" --ignore="$ROOT/compiler/tests/runtime"
UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" python -m compileall -q "$ROOT/compiler/src"
UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" "$ROOT/scripts/regenerate.sh"
UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" python "$ROOT/scripts/verify_generated.py"
