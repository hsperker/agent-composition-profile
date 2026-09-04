# Agent Composition Profile runtime evidence

**Experiment date:** 3 September 2026

**Portable fixture:** `examples/research-team/` (unchanged)

**Additional probe:** `examples/runtime-probes/delegation/` (only isolates delegation from the fixture's intentionally unreachable MCP endpoint)

## Result

The proposed profile is not one coherent portable runtime abstraction.

Two semantics survived as a convincing core: a logical agent identity and persistent behavioral instructions. Description, Agent Skills, and Agent Plugins remain useful optional composition semantics, but strict runtimes must reject them when their authority, scope, or lifecycle cannot be preserved. Model capability policy belongs to deployment. The current `delegates` contract is false as a cross-framework abstraction and should leave the portable core.

This is not a majority vote. The recommendations below use the semantic intersection actually observed. A framework accepting similarly named constructor arguments does not count as preservation.

The classifications are recorded reviewer judgments about each native mechanism. Each adapter states its grade and rationale explicitly, the tests assert those grades, and the construction and runtime observations back them. The grades are not derived from the traces by measurement. The runtime runs use scripted deterministic models, so they prove that instructions, tool calls, and returns travel through the real framework code paths, not that any model behaves differently as a result. Read the matrix as a structured, reproducible assessment, not as an instrument reading.

| Source semantic | Recommendation | Narrow semantic that survived |
|---|---|---|
| `name` | **CORE** | Stable logical identity, with an explicit reversible native-name resolver where necessary. |
| Markdown instructions | **CORE** | Persistent authoritative behavioral context on every invocation. |
| `description` | **OPTIONAL** | Human-readable selection/discovery hint; it must not silently become behavioral instructions. |
| `model.requires` | **HOST** | Deployment precondition attested by a model binding, not an agent-runtime primitive. |
| `model.prefers` | **REMOVE** | Non-binding deployment preference with no portable behavioral guarantee. |
| `skills` | **OPTIONAL** | Agent-private Agent Skills catalog with metadata-first, instruction-authority activation. |
| `plugins` | **OPTIONAL** | Required expansion of all standard Agent Plugin components into agent-scoped capabilities. |
| `delegates` | **REMOVE** | No coherent invocation semantic; retain agent package composition only as a convention. |

## What ran

Each environment is independently locked because a single environment is impossible: CrewAI 1.15.18 requires `openai>=2.30,<3`, while OpenAI Agents 0.22.0 requires `openai>=3,<4`. Python 3.13 was used because CrewAI's transitive Chroma/Pydantic v1 path failed to import on Python 3.14.

| Runtime | Tested version | Native objects constructed | Runtime exercised | Full fixture strict result |
|---|---:|---|---|---|
| LangChain / LangGraph | LangChain 1.4.0; LangGraph 1.2.11 | `CompiledStateGraph`, `StructuredTool` | Parent → child agent-tool → parent | Rejected |
| CrewAI | 1.15.18 | `Agent`, `Crew`, native Skills, MCP configs | Leaf `Agent.kickoff`; native skill load | Rejected |
| LlamaIndex | core 0.14.24 | `FunctionAgent`, `AgentWorkflow`, `BasicMCPClient` | Leaf `FunctionAgent.run` | Rejected |
| Agno | 3.0.5 | `Agent`, `Team`, `Skills`, `MCPTools` | Leaf `Agent.run`; native skill load | Rejected |
| OpenAI Agents SDK | 0.22.0 | `Agent`, MCP servers, agent tools | Parent → child `Agent.as_tool` → parent | Rejected |
| Google ADK | 2.8.0 | `LlmAgent`, `AgentTool`, `McpToolset` | Parent → nested AgentTool → parent | Rejected |
| PydanticAI | 2.38.0 | `Agent`, `Tool`, `MCPToolset` | Parent → async adapter tool → child → parent | Rejected |
| Microsoft Agent Framework | 1.17.0 | `Agent`, `SkillsProvider`, MCP tools, agent tools | Parent → child `Agent.as_tool` → parent | Rejected |

The runtime traces are under `generated/runtime/<target>/runtime.json`; each directory also contains `test-output.txt`. Individual compatibility reports are under `generated/runtime/<target>/compatibility.json`. `generated/runtime/matrix.json` and `matrix.md` are generated from those eight reports plus the still-valid static-lowering reports for Amplifier, Claude Code, Codex, and AFM. The matrix labels evidence kind; static lowering is not presented as runtime certification. It also records hashes for every unchanged research-fixture file.

CrewAI, Agno, and LlamaIndex multi-agent objects were constructed but their team/workflow transitions were not forced with invented orchestration. The profile does not contain the task graph, process, shared-state, or routing policy those mechanisms require. That underdetermination is evidence against `delegates`, not a reason to fabricate a passing run.

## Classification matrix

This table summarizes the entry agent. Machine-readable agent-by-agent details and explanations remain authoritative.

| Target | name | description | instructions | requires | prefers | skills | plugins | delegates |
|---|---|---|---|---|---|---|---|---|
| LangGraph | preserved | unsupported | preserved | resolved | omitted | approximated | unsupported | approximated |
| CrewAI | approximated | approximated | approximated | resolved | omitted | approximated | resolved | approximated |
| LlamaIndex | preserved | preserved | preserved | resolved | omitted | approximated | unsupported | approximated |
| Agno | preserved | approximated | preserved | resolved | omitted | approximated | resolved | approximated |
| OpenAI Agents | preserved | preserved | preserved | resolved | omitted | approximated | resolved | preserved |
| Google ADK | resolved | preserved | preserved | resolved | omitted | approximated | resolved | approximated |
| PydanticAI | preserved | preserved | preserved | resolved | omitted | approximated | resolved | approximated |
| Microsoft Agent Framework | preserved | preserved | preserved | resolved | omitted | approximated | resolved | preserved |
| Amplifier (static) | preserved | preserved | preserved | resolved | resolved | unsupported | unsupported | preserved |
| Claude Code (static) | preserved | preserved | preserved | resolved | resolved | resolved | resolved | preserved |
| Codex (static) | preserved | preserved | preserved | resolved | resolved | resolved | resolved | resolved |
| AFM 0.4.0 (static) | preserved | preserved | preserved | resolved | resolved | preserved | resolved | unsupported |

`requires` combines the fixture's `reasoning` and `tool-use` rows; every runtime result is a binding attestation, not native capability proof. `prefers` abbreviates `omitted-preference` for runtime targets. The earlier static targets used a binding that selected the preferred capability, so their result is `resolved`.

## Field findings

### `name` — CORE

Observed mechanisms:

- LangGraph, LlamaIndex, Agno, OpenAI Agents, PydanticAI, and Microsoft have native name fields.
- CrewAI has a role, not a stable agent identity; using the source name as role changes its semantics.
- Google ADK rejects `lead-researcher` because names must be valid Python identifiers. The adapter uses `lead_researcher` and retains an explicit source/native identity map.
- The four static targets have native identity fields.

Intersection: a stable logical identity is necessary for references, diagnostics, and package resolution. Native spelling is not portable.

Important difference: a runtime identifier may have a stricter grammar or may double as prompt content.

Recommendation: keep `name` in the core, define it as the package-level logical identity, and permit only deterministic, collision-checked, reversible native-name resolution. Do not claim byte-for-byte native preservation when a resolver is used.

### `description` — OPTIONAL

Observed mechanisms:

- Google ADK, LlamaIndex, OpenAI Agents, PydanticAI, and Microsoft expose native description or handoff-description metadata.
- LangGraph's compiled entry agent has no description property; a child description only exists when that child is wrapped as a tool.
- Agno injects description into model context.
- CrewAI's closest field is `goal`, which is behavioral prompt content rather than passive selection metadata.

Intersection: a human-readable hint about what an agent does and when to select it.

Important difference: discovery metadata, routing metadata, tool description, and behavioral goal are not interchangeable. Promotion into instructions can change output.

Recommendation: retain description only as optional selection/discovery metadata. A target that can only inject it as behavioral prompt content must report `approximated`; strict mode rejects that mapping.

### Markdown instructions — CORE

Observed mechanisms:

- LangGraph, LlamaIndex, Agno, OpenAI Agents, Google ADK, PydanticAI, Microsoft, and the static targets provide persistent instruction/system-prompt paths.
- Google ADK's string instructions perform `{state_key}` interpolation; the adapter uses a native instruction callback so arbitrary Markdown remains literal.
- Microsoft passes instructions through chat options to the client rather than inserting a `system` message itself; the nested runtime recorded the child instructions in those options.
- CrewAI embeds the body as `backstory` within a generated role/goal/backstory prompt template. The instructions run, but their boundary and authority are changed.

Intersection: persistent behavioral context applied on every invocation, distinct from ordinary task input and tool output.

Important difference: exact provider message role is not portable. Instruction authority is.

Recommendation: keep the Markdown body in the core. Define semantic preservation by persistence and authority, not by a required provider message role or byte-identical final prompt.

### `model.requires` — HOST

Observed mechanism in all eight runtime adapters: the profile parser exposes capability names, but the framework model objects do not provide a common, trustworthy capability contract. Every successful result came from an external binding assertion such as `tool-use: true`.

Intersection: a deployment can refuse to bind a model that does not satisfy a declared precondition.

Important differences:

- `tool-use` can sometimes be inferred from model/tool APIs, but support may depend on provider, selected model, or request mode.
- `reasoning` has no shared operational definition across the SDKs.
- Capability names, evidence, and fallback policy are deployment concerns.

Recommendation: move required model capability policy to the host binding. If a future profile references a governed capability vocabulary, treat it as a deployment preflight contract and require recorded attestation; do not imply that the runtime SDK verified it.

### `model.prefers` — REMOVE

Observed mechanism: all runtime experiments deliberately bound models without the preferred `vision-input` and reported `omitted-preference`. Execution behavior was unchanged, as required for a preference.

Intersection: none beyond a non-binding deployment hint.

Important difference: model selectors use incompatible vocabularies and ranking rules.

Recommendation: remove `model.prefers` from the portable agent document. Put model-selection preferences in target bindings or deployment policy, where ignoring them cannot be confused with semantic preservation.

### `skills` — OPTIONAL

Observed mechanisms:

- CrewAI, Agno, and Microsoft have native Agent Skills implementations. Tests proved metadata-only discovery and then invoked the native loader. In all three the loader is a framework-provided tool (CrewAI `LoadSkillTool`, Agno `get_skill_instructions`, Microsoft `SkillsProvider` `load_skill`) and the activated body returns as tool output. Microsoft additionally gates `load_skill` behind approval by default; the adapter disables that gate and reports it.
- Claude Code, Codex, and AFM have still-valid static Agent Skills mappings, with scope differences documented in their reports.
- LangGraph, LlamaIndex, OpenAI Agents, Google ADK, and PydanticAI have no native Agent Skills support; the adapter exposes an activation tool with the same tool-output result.
- Whether the framework or the adapter authored the tool does not change what enters model context. All eight runtime targets are therefore `approximated`. The native implementations add resource access, script execution, events, and approvals, which is real value, but not instruction authority.
- Amplifier's direct static mapping remains unsupported without a runtime module.

Intersection: an agent-private catalog identified by name and description, with full instructions disclosed only when activated.

Important differences: catalog scope, activation persistence, instruction authority, approval, resource access, and script execution. Loading a file into process memory is not the relevant disclosure boundary; putting its body into model context is.

Recommendation: retain Agent Skill references as an optional composed capability. Preservation requires Agent Skills semantics, including metadata-first disclosure and instruction-authority activation. A tool that merely returns `SKILL.md` text is an approximation and blocks strict execution. No tested runtime met that bar; only the static Claude Code, Codex, and AFM mappings did, and those are unexecuted.

### `plugins` — OPTIONAL

Observed mechanisms:

- CrewAI, Agno, OpenAI Agents, Google ADK, PydanticAI, and Microsoft construct native agent-scoped MCP clients/toolsets from the Agent Plugin MCP server.
- LangGraph and LlamaIndex can construct clients, but the experiment could not attach usable native tools without activating the deliberately unavailable fixture endpoint. They report unsupported rather than inventing tools.
- Static Claude, Codex, and AFM mappings resolve supported plugin components; Amplifier still needs a runtime shim.

Intersection: an Agent Plugin reference is a required package dependency whose standard components expand into the effective agent capability set.

Important differences: the plugin wrapper disappears after expansion; MCP connection ownership, activation timing, headers, working directory, approvals, and tool catalog scope vary. Construction proves representability, not endpoint availability. The example endpoint was intentionally not treated as live.

Recommendation: retain plugin references as optional composition. Strict mode must preserve every valid standard component and agent scope or reject. Runtime activation failures remain invocation failures. The profile must not standardize plugin lifecycle beyond what Agent Plugins and MCP already define.

### `delegates` — REMOVE

Observed mechanisms:

- LangGraph: no agent relationship primitive; an adapter-authored `StructuredTool` starts a fresh child graph and returns text. Graded `approximated`, because the adapter, not the framework, chose that policy.
- OpenAI Agents and Microsoft: native agent-as-tool; Microsoft explicitly defaults to an independent child session.
- PydanticAI: no agent relationship primitive; an async adapter `Tool` can reproduce bounded text-in/text-out behavior, graded `approximated` for the same reason as LangGraph. A first synchronous implementation failed at runtime because nested `run_sync()` is forbidden.
- Google ADK: `AgentTool` creates a child session but copies parent state and propagates child state deltas back.
- LlamaIndex: `AgentWorkflow.can_handoff_to` transfers active control through shared workflow state.
- Agno: `Team` expresses team/member collaboration.
- CrewAI: delegation is coupled to Crew tasks, context, and process.
- Codex exposes a project catalog rather than the same per-parent contract; AFM 0.4.0 has no local equivalent.

Intersection: other named agents may be available. There is no shared answer to who retains control, whether state is shared, whether the child is a tool, whether a workflow transition occurs, or what task/result contract applies.

Important difference: these mechanisms change observable behavior. Treating a handoff or shared team as a fresh child function call is not lowering; it is inventing an orchestration policy.

Recommendation: remove `delegates` and its fresh text-in/text-out contract from the portable core. If package composition is needed, use a non-behavioral `agents:` inventory convention or an external manifest. Invocation relationships should be expressed by a separately typed mechanism (`agent-as-tool`, `handoff`, `workflow-transition`, `team-member`, or host-specific), not one overloaded field.

## Strict-mode result

Strict construction rejects any required semantic classified `approximated` or `unsupported`; it never discards one. `omitted-preference` is non-blocking. Every report contains exactly one finding for every semantic declared by every source agent.

No runtime target accepted the full research fixture. Microsoft Agent Framework came closest and was rejected only because skill activation returns tool output. The failures reveal where the proposed declaration demands semantics their targets do not share.

## Proposed profile changes

1. Reduce the required document to `name` plus Markdown instructions.
2. Make `description`, `skills`, and `plugins` optional semantics with strict preservation rules.
3. Remove `model` from the portable document; keep capability attestations and preferences in external target bindings.
4. Remove `delegates` from the profile. Allow package inventory as a convention without promising an invocation mechanism.
5. Preserve the diagnostic vocabulary: `preserved`, `resolved`, `approximated`, `unsupported`, and `omitted-preference` for legacy reports only. New core reports need no preference status after `model.prefers` is removed.
6. Require adapters to distinguish construction, activation, and execution evidence.
7. Continue to forbid in-document host extensions. Target bindings remain external.

## Limits

- Deterministic fake/model subclasses avoided paid network inference but used each framework's real agent, tool, workflow/team, and runner code paths.
- The fixture's `https://research.example.com/mcp` endpoint is illustrative and unreachable. MCP client construction was tested; a live cross-framework server handshake was not claimed.
- The four earlier targets remain static-lowering evidence only.
- No conclusion depends on generated answer quality. The experiment tests representation, authority, scope, and control flow.
- Instruction authority was judged from each framework's mechanism, not measured. No test observes whether activated skill text changes model behavior differently from a system prompt.
- Strict acceptance or rejection of the full fixture is a construction result. No full-fixture run reached a live MCP endpoint.
