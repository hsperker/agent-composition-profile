# Agent Profile interoperability experiment

A portable agent profile must lower into the tools people actually run agents in. Otherwise it is a schema, not a profile. This repository tests how much of a candidate Agent Profile survives that lowering, and uses agent frameworks as a check on the semantics.

**Success test.** One profile, compiled by the reference compiler into the directories of several products, runs in each without hand edits. Where it does not, the compatibility report says which field was lost and why.

## Two dimensions

**Products** are where customers run agents without writing code, so they are the destinations that make ownership real: whoever holds the file can leave whichever host produced it. A product qualifies as a target when it reads agent definitions from files the customer controls. Today: Claude Code, Codex, GitHub Copilot, OpenCode, and, from the earlier static work, Amplifier and AFM. Chat applications that keep agent configuration in a vendor UI do not qualify. Product evidence is static for most products: the compiler produces the files and verifies them. Claude Code, Codex, Copilot CLI, and OpenCode (v1 and v2) are also executed: the generated project runs headless against a scripted model endpoint and the probe records what reached the model.

**Frameworks** are where developers embed agents in their own software. They are canaries: eight of them show which semantics are safe to promise and where a profile stops being a profile and becomes code generation. Framework evidence is executed: adapters build native objects and run them with deterministic models.

The frameworks are LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, and Microsoft Agent Framework.

## What survived

The candidate had eight fields: `name`, `description`, Markdown instructions, `model.requires`, `model.prefers`, Agent Skills, Agent Plugins, `delegates`.

```text
Required     name, Markdown instructions
Optional     description, skills, plugins, subagents
Incubating   model.requires
Removed      model.prefers, generic delegates
```

- All six product targets and seven of eight frameworks preserve the core. CrewAI does not: its role, goal, and backstory template fuses identity, description, and instructions.
- Optional fields follow one rule. If the field is present, a strict host preserves its defined semantics or rejects the profile. A skill or plugin reference means availability to the agent, not isolation.
- Model requirements belong to the author and are resolved by the host, but no capability vocabulary is standardized yet.
- `delegates` hid six mechanisms behind one word and is gone. One of them survives as `subagents`: a listed agent invoked as a bounded task with its own instructions, returning a result while the caller keeps control. Claude Code, OpenCode, and Amplifier preserve it, Codex and Copilot CLI resolve it because their catalogs are project wide and the list is not enforced, AFM has no equivalent; orchestration first frameworks only approximate it.
- One Agent Plugin with a local MCP server activated in all eight frameworks over stdio and header gated streamable HTTP. Two SDKs cannot set a working directory, so speaking MCP is not the same as supporting Agent Plugins. The tool names a model sees are not portable.

Grades are reviewer judgments backed by tests, not measurements. Anything not exercised is marked `unverified`.

[EVIDENCE.md](EVIDENCE.md) has the findings. The [draft profile](spec/agent-composition-profile-v0.2-discussion-draft.md) has the resulting shape. [EXTERNAL-PROPOSAL.md](EXTERNAL-PROPOSAL.md) frames the work for the Agent Plugins incubation.

## Reproduce

```bash
./scripts/verify.sh          # parser, product targets, generated artifacts
./scripts/verify-runtime.sh  # eight locked framework environments, native tests, probes, matrix
./scripts/verify-products.sh # installed product CLIs headless against a scripted endpoint
```

Each framework has its own hash locked environment under `compiler/runtime-requirements/`, because CrewAI and OpenAI Agents need incompatible major versions of `openai`. Everything under `generated/` is produced by the scripts and never edited by hand.

## Map

```text
compiler/src/agent_profile_compiler/targets/  product targets (static lowering)
compiler/src/agent_profile_compiler/runtime/  framework adapters (executed)
compiler/src/agent_profile_compiler/products/ product probes and the scripted Anthropic endpoint
compiler/tests/                               parser, target, and runtime tests
compiler/runtime-requirements/                per framework pins and hash locks
examples/research-team/                       the unchanged fixture
examples/runtime-probes/delegation/           offline control flow probe
examples/runtime-probes/plugin-activation/    one plugin, local MCP echo server
generated/                                    product outputs, framework reports, product probes, matrix
spec/                                         draft 0.2 and its schema
docs/                                         provenance, discussion post draft
```
