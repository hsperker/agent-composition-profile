#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/compiler/src"
BINDING="$ROOT/bindings/example-bindings.yaml"
PACKAGE="$ROOT/examples/research-team"

compile() {
  local name="$1"
  local entry="$2"
  local target="$3"
  shift 3
  local output="$ROOT/generated/$name"
  rm -rf "$output"
  python -m agent_profile_compiler.cli \
    "$entry" \
    --package-root "$PACKAGE" \
    --target "$target" \
    --binding "$BINDING" \
    --output "$output" \
    "$@"
}

compile amplifier-critic-strict "$PACKAGE/agents/critic.agent.md" amplifier
compile amplifier-full-diagnostic "$PACKAGE/lead.agent.md" amplifier --diagnostic
compile claude-code-full-strict "$PACKAGE/lead.agent.md" claude-code
compile codex-full-strict "$PACKAGE/lead.agent.md" codex
compile afm-explorer-strict "$PACKAGE/agents/explorer.agent.md" afm
compile afm-full-diagnostic "$PACKAGE/lead.agent.md" afm --diagnostic
