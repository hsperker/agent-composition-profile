# Runtime evidence for the Agent Plugins Agent Profile incubation

We investigated the Agent Profile idea already under discussion here rather than designing a new specification. We tested a candidate semantic model against eight live framework runtimes and four additional declarative targets, and this note reports what actually survived. The eight SDKs were LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, and Microsoft Agent Framework. The experiment instantiated native agents, exercised framework runners with scripted deterministic models, and classified every declared semantic without silently discarding failures. The classifications are recorded reviewer judgments about each native mechanism, graded against the published Agent Skills, Agent Plugins, and MCP contracts and backed by construction tests and runtime smoke tests, not measurements derived from traces. Conformance is reported for the required core and for each optional field: seven of eight runtimes accept the core, and three accept the combined fixture with skill durability under compaction and on-demand skill resources still unverified. Earlier static-lowering evidence for Amplifier, Claude Code, Codex, and AFM remains labeled separately.

The result argues for a smaller Agent Profile inside the existing Agent Plugins incubation effort, not a competing standard.

The strongest common semantics were:

- a stable logical agent name as required metadata, allowing explicit reversible native aliases;
- persistent Markdown instructions with instruction authority;
- optional selection metadata;
- model requirements as a coherent concept, declared by the author and resolved by the host, though without a standardized capability vocabulary yet;
- optional Agent Skills and Agent Plugins references, with strict preservation of their lower-layer semantics. Every runtime activated skills through the dedicated-tool pattern of the Agent Skills integration guide; none exercised session durability.

Two proposed areas did not survive as written:

- Model preferences and selection were only deployment policy. Requirements survive as a declaration, but `reasoning` lacks a shared operational definition, and no SDK verified any capability natively.
- `delegates` conflated agent-as-tool, handoff, graph transition, shared-state execution, and team collaboration. Those mechanisms differ in control, context, and result semantics. One field should not pretend they are one thing.

The proposed incubation direction is:

1. Start with `name` plus persistent Markdown instructions as the core.
2. Treat `description`, Agent Skills, and Agent Plugins as optional fields with one rule: if present, a strict host preserves their defined semantics or rejects the profile. Profile strictness is a composition-level rule and does not change Agent Plugins' own incremental conformance.
3. Incubate `model.requires` as a host-resolved declaration until the capability vocabulary is standardized; keep model selection, preferences, and attestation in deployment bindings.
4. Add no agent inventory or relationship field. An Agent Profile describes one agent; packaging and orchestration are separate concerns.
5. Require compatibility reports to distinguish native construction, activation, and execution using `preserved`, `resolved`, `approximated`, `unsupported`, and `unverified`.

The useful result is the failed abstraction: portable agent packaging appears viable, but portable orchestration does not follow merely because frameworks all use the word “agent.” The executable adapters, exact dependency locks, reports, traces, and generated matrix are available as implementation evidence for further incubation work.
