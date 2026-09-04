# Agent Composition Profile Reference Compiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Revise the discussion draft to remove in-document host extensions and prove the proposed semantic core with a tested reference compiler for several existing harness formats.

**Architecture:** A strict parser loads one Markdown declaration and its local delegate graph. Target adapters lower that graph into native artifacts and emit a machine-readable compatibility report. Host-specific model choices and capability attestations enter through an external compiler binding file, never through the portable source.

**Tech Stack:** Python 3.13, PyYAML, jsonschema, pytest, standard-library TOML parsing.

**Spec:** `spec/agent-composition-profile-v0.1-discussion-draft.md`

## Global Constraints

- The portable declaration contains no format identifier and no host-extension field during the discussion-draft phase.
- Core fields are `name`, `description`, `model`, `skills`, `plugins`, and `delegates`; the Markdown body supplies instructions.
- Generated target files are build artifacts, not sources of truth.
- Every adapter emits `preserved`, `resolved`, `approximated`, `unsupported`, and `omitted-preference` findings.
- Strict compilation fails on any unsupported required semantic.

---

### Task 1: Parser and package model

**Files:**
- Create: `compiler/src/agent_profile_compiler/model.py`
- Create: `compiler/src/agent_profile_compiler/parser.py`
- Create: `compiler/tests/test_parser.py`
- Create: `spec/agent-composition-profile-v0.1-frontmatter.schema.json`

- [x] Write tests for valid declarations, unknown fields, aliases, empty bodies, duplicate names, cycles, and path containment.
- [x] Run the tests and verify they fail because parser code is absent.
- [x] Implement the smallest parser and recursive package loader that passes them.
- [x] Run parser tests and verify they pass.

### Task 2: Target adapters and loss reports

**Files:**
- Create: `compiler/src/agent_profile_compiler/report.py`
- Create: `compiler/src/agent_profile_compiler/compiler.py`
- Create: `compiler/src/agent_profile_compiler/targets/amplifier.py`
- Create: `compiler/src/agent_profile_compiler/targets/claude_code.py`
- Create: `compiler/src/agent_profile_compiler/targets/codex.py`
- Create: `compiler/src/agent_profile_compiler/targets/afm.py`
- Create: `compiler/tests/test_targets.py`

- [x] Write failing tests for native file shapes, external model bindings, delegate lowering, plugin MCP lowering, and strict rejection of semantic gaps.
- [x] Run target tests and verify they fail because adapters are absent.
- [x] Implement target adapters and structured compatibility reports.
- [x] Run all tests and verify they pass.

### Task 3: Examples, generated artifacts, and revised draft

**Files:**
- Create: `examples/research-team/**`
- Create: `bindings/example-bindings.yaml`
- Generate: `generated/*/**`
- Create: `docs/IMPLEMENTATION_REPORT.md` and `docs/LOWERING_WALKTHROUGH.md`
- Create: `README.md`
- Create: `spec/agent-composition-profile-v0.1-discussion-draft.md`

- [x] Add a representative package with direct skills, an Agent Plugin, and two delegates.
- [x] Compile it for all targets in diagnostic mode and capture the reports.
- [x] Add strict leaf-agent cases that compile without semantic loss where supported.
- [x] Revise the draft: rename it, remove `spec` and `extensions`, add external bindings, add AFM/OAF findings, and replace speculative mappings with measured compiler results.
- [x] Run schema, parser, compiler, TOML, YAML, Markdown-fence, and generated-file checks.
