# Runtime evidence for the Agent Plugins Agent Profile incubation

We tested the current Agent Composition Profile hypothesis against eight stable Python SDKs: LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, and Microsoft Agent Framework. The experiment instantiated native agents, exercised framework runners with scripted deterministic models, and classified every declared semantic without silently discarding failures. The classifications are recorded reviewer judgments about each native mechanism, graded against the published Agent Skills, Agent Plugins, and MCP contracts and backed by construction tests and runtime smoke tests, not measurements derived from traces. Conformance is reported per module: seven of eight runtimes accept the core, and three accept the combined fixture with skill durability under compaction still unverified. Earlier static-lowering evidence for Amplifier, Claude Code, Codex, and AFM remains labeled separately.

The result argues for a smaller Agent Profile inside the existing Agent Plugins incubation effort, not a competing standard.

The strongest common semantics were:

- a stable logical agent name as required metadata, allowing explicit reversible native aliases;
- persistent Markdown instructions with instruction authority;
- optional selection metadata;
- optional model requirements, declared by the author and resolved by the host;
- optional Agent Skills and Agent Plugins references, with strict preservation of their lower-layer semantics. Every runtime activated skills through the dedicated-tool pattern of the Agent Skills integration guide; none exercised session durability.

Two proposed areas did not survive as written:

- Model preferences and selection were only deployment policy. Requirements survive as a declaration, but `reasoning` lacks a shared operational definition, and no SDK verified any capability natively.
- `delegates` conflated agent-as-tool, handoff, graph transition, shared-state execution, and team collaboration. Those mechanisms differ in control, context, and result semantics. One field should not pretend they are one thing.

The proposed incubation direction is:

1. Start with `name` plus persistent Markdown instructions as the core.
2. Treat `description`, `model.requires`, Agent Skills, and Agent Plugins as optional capability modules, mirroring Agent Plugins' partial component support, with conformance reported per module.
3. Keep model selection, preferences, and attestation in external deployment bindings; keep the requirement declaration with the agent.
4. Keep agent inventory as a non-behavioral package convention until typed relationship mechanisms have independent evidence.
5. Require compatibility reports to distinguish native construction, activation, and execution using `preserved`, `resolved`, `approximated`, `unsupported`, and `unverified`.

The useful result is the failed abstraction: portable agent packaging appears viable, but portable orchestration does not follow merely because frameworks all use the word “agent.” The executable adapters, exact dependency locks, reports, traces, and generated matrix are available as implementation evidence for further incubation work.
