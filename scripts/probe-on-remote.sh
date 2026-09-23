#!/usr/bin/env bash
set -euo pipefail

# Run a product probe on a remote machine where the product CLI is installed
# (for example a Raspberry Pi with Codex) and copy the evidence back.
#
#   scripts/probe-on-remote.sh <ssh-host> <product>
#
# The repository is synced to ~/agent-composition-profile on the remote, a
# virtual environment with the compiler's dependencies is created there, and
# scripts/run_product_probe.py runs. Only generated/products/ comes back.

HOST="${1:?ssh host}"
PRODUCT="${2:?product}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_DIR="agent-composition-profile"

rsync -az --delete --exclude .git --exclude compiler/.venv --exclude .probe-venv --exclude '__pycache__' --exclude .pytest_cache \
  "$ROOT/" "$HOST:$REMOTE_DIR/"

ssh "$HOST" REMOTE_DIR="$REMOTE_DIR" PRODUCT="$PRODUCT" bash -s <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"
[ -x .probe-venv/bin/pip ] || { rm -rf .probe-venv; python3 -m venv .probe-venv; }
.probe-venv/bin/pip install -q PyYAML==6.0.3 jsonschema==4.26.0 mcp
# Plugin MCP servers start with a bare `python`; it must resolve to the venv that has `mcp`.
PATH="$PWD/.probe-venv/bin:$PATH" PYTHONPATH=compiler/src python scripts/run_product_probe.py "$PRODUCT"
REMOTE

rsync -az "$HOST:$REMOTE_DIR/generated/products/" "$ROOT/generated/products/"
echo "evidence copied to generated/products/"
