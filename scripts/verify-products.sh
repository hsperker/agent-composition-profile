#!/usr/bin/env bash
set -euo pipefail

# Product probes run the installed product CLI headless against a scripted model endpoint.
# A product that is not installed is skipped and reported; it does not fail the run.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE_DIR="${ACP_UV_CACHE_DIR:-/tmp/uv-cache-agent-composition-profile}"
LOCK="$ROOT/compiler/runtime-requirements/products.lock"
UV=(uv run --python 3.13 --project "$ROOT/compiler" --extra test --with-requirements "$LOCK")

mkdir -p "$ROOT/generated/products"
UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" pytest -q "$ROOT/compiler/tests/products" -p no:warnings \
  2>&1 | tee "$ROOT/generated/products/test-output.txt"

for product in claude-code opencode codex; do
  UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" python "$ROOT/scripts/run_product_probe.py" "$product" || true
done

UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" python "$ROOT/scripts/build_runtime_matrix.py"
UV_CACHE_DIR="$CACHE_DIR" "${UV[@]}" python "$ROOT/scripts/verify_generated.py"
