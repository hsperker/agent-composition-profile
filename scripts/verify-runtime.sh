#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${ACP_UV_CACHE_DIR:-/tmp/uv-cache-agent-composition-profile}"

mkdir -p "$ROOT/generated/runtime"
UV_CACHE_DIR="$CACHE_DIR" uv run \
  --python 3.13 \
  --project "$ROOT/compiler" \
  --extra test \
  pytest -q \
  "$ROOT/compiler/tests/runtime/test_contract.py" \
  "$ROOT/compiler/tests/runtime/test_capabilities.py" \
  "$ROOT/compiler/tests/runtime/test_registry.py" \
  2>&1 | tee "$ROOT/generated/runtime/shared-test-output.txt"

run_target() {
  local target="$1"
  local test_file="$2"
  local lock="$ROOT/compiler/runtime-requirements/$target.lock"
  local output_dir="$ROOT/generated/runtime/$target"
  mkdir -p "$output_dir"

  UV_CACHE_DIR="$CACHE_DIR" uv run \
    --python 3.13 \
    --project "$ROOT/compiler" \
    --extra test \
    --with-requirements "$lock" \
    pytest -q "$ROOT/compiler/tests/runtime/$test_file" \
    2>&1 | tee "$output_dir/test-output.txt"

  UV_CACHE_DIR="$CACHE_DIR" uv run \
    --python 3.13 \
    --project "$ROOT/compiler" \
    --extra test \
    --with-requirements "$lock" \
    python "$ROOT/scripts/run_runtime_probe.py" "$target"
}

run_target langgraph test_langgraph_runtime.py
run_target crewai test_crewai_runtime.py
run_target llamaindex test_llamaindex_runtime.py
run_target agno test_agno_runtime.py
run_target openai-agents test_openai_agents_runtime.py
run_target google-adk test_google_adk_runtime.py
run_target pydantic-ai test_pydantic_ai_runtime.py
run_target microsoft-agent-framework test_microsoft_agent_framework_runtime.py

UV_CACHE_DIR="$CACHE_DIR" uv run \
  --python 3.13 \
  --project "$ROOT/compiler" \
  --extra test \
  python "$ROOT/scripts/build_runtime_matrix.py"

UV_CACHE_DIR="$CACHE_DIR" uv run \
  --python 3.13 \
  --project "$ROOT/compiler" \
  --extra test \
  python "$ROOT/scripts/verify_generated.py"
