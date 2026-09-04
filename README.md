# Agent Composition Profile interoperability experiment

One question: which parts of a small agent declaration mean the same thing across independent agent frameworks?

We took a candidate profile with eight fields (`name`, `description`, Markdown instructions, `model.requires`, `model.prefers`, Agent Skills, Agent Plugins, `delegates`) and built the same fixture in eight framework runtimes and four declarative formats. Each adapter constructs native objects, runs them with deterministic models, and grades every field against the published Agent Skills, Agent Plugins, and MCP contracts. The runtimes are LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, and Microsoft Agent Framework. The formats are Amplifier, Claude Code, Codex, and AFM.

## What survived

```text
Required     name, Markdown instructions
Optional     description, skills, plugins
Incubating   model.requires
Removed      model.prefers, delegates
```

- Seven of eight runtimes preserve the core. CrewAI does not: its role, goal, and backstory template fuses identity, description, and instructions, and its template override only collapses everything into one user message.
- Optional fields follow one rule. If the field is present, a strict host preserves its defined semantics or rejects the profile.
- Model requirements belong to the author and are resolved by the host. No capability vocabulary is standardized yet, so the field stays incubating.
- `delegates` hid six different mechanisms behind one word.
- One Agent Plugin with a local MCP server activated in all eight runtimes over stdio and header gated streamable HTTP. Two SDKs cannot set a working directory, so speaking MCP is not the same as supporting Agent Plugins. The tool names a model sees are not portable.

Grades are reviewer judgments backed by tests, not measurements. Anything not exercised is marked `unverified`.

[EVIDENCE.md](EVIDENCE.md) has the findings. The [draft profile](spec/agent-composition-profile-v0.2-discussion-draft.md) has the resulting shape. [EXTERNAL-PROPOSAL.md](EXTERNAL-PROPOSAL.md) frames the work for the Agent Plugins incubation.

## Reproduce

```bash
./scripts/verify.sh          # parser, static targets, generated artifacts
./scripts/verify-runtime.sh  # eight locked environments, native tests, probes, matrix
```

Each runtime has its own hash locked environment under `compiler/runtime-requirements/`, because CrewAI and OpenAI Agents need incompatible major versions of `openai`. Everything under `generated/runtime/` is produced by the scripts and never edited by hand.

## Map

```text
compiler/src/agent_profile_compiler/runtime/  the eight runtime adapters
compiler/tests/runtime/                       native construction and runtime tests
compiler/runtime-requirements/                per framework pins and hash locks
examples/research-team/                       the unchanged fixture
examples/runtime-probes/delegation/           offline control flow probe
examples/runtime-probes/plugin-activation/    one plugin, local MCP echo server
generated/runtime/                            reports, traces, matrix
spec/                                         draft 0.2 and its schema
docs/                                         static lowering provenance, discussion post draft
```
