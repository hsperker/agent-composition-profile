# Agent Composition Profile runtime evidence

**Experiment date:** 3 September 2026

**Portable fixture:** `examples/research-team/` (unchanged)

**Additional probe:** `examples/runtime-probes/delegation/` (only isolates delegation from the fixture's intentionally unreachable MCP endpoint)

## Result

The proposed profile is not one coherent portable runtime abstraction.

Two semantics survived as a convincing core: a logical agent identity as required metadata and persistent behavioral instructions as the one core behavioral semantic. Description, model requirements, Agent Skills, and Agent Plugins are optional capability modules: a host declares which it implements and must preserve every declared semantic of those modules or reject strictly. Model requirements are declared by the agent author and resolved by the host. The generic `delegates` field overloads several incompatible mechanisms and should leave the profile.

This is not a majority vote. The recommendations below use the semantic intersection actually observed. A framework accepting similarly named constructor arguments does not count as preservation.

The classifications are recorded reviewer judgments about each native mechanism, graded against the published Agent Skills, Agent Plugins, and MCP contracts. Each adapter states its grade and rationale explicitly, the tests assert those grades, and the construction and runtime observations back them. The grades are not derived from the traces by measurement. The runtime runs use scripted deterministic models, so they prove that instructions, tool calls, and returns travel through the real framework code paths, not that any model behaves differently as a result. A property that was not exercised is recorded as `unverified`, never as `approximated`. Read the matrix as a structured, reproducible assessment, not as an instrument reading.

| Source semantic | Recommendation | Narrow semantic that survived |
|---|---|---|
| `name` | **REQUIRED METADATA** | Stable logical identity for discovery, diagnostics, and packaging, with an explicit reversible native-name resolver where necessary. Not itself a runtime behavior. |
| Markdown instructions | **CORE** | Persistent authoritative behavioral context on every invocation. |
| `description` | **OPTIONAL MODULE** | Metadata to understand, display, discover, or select the agent; it must not be merged into behavioral instructions. A catalog profile may require it. |
| `model.requires` | **OPTIONAL MODULE, HOST RESOLVED** | Declared by the agent author, attested by the host binding. `reasoning` lacks a shared operational definition. |
| `model.prefers` | **REMOVE** | Non-binding deployment selection policy; belongs in the host binding. |
| `skills` | **OPTIONAL MODULE** | Additive Agent Skills declaration with metadata-first, on-demand activation per the Agent Skills integration guide. Session durability is unverified everywhere. |
| `plugins` | **OPTIONAL MODULE** | Required expansion of all standard Agent Plugin components into agent-scoped capabilities. |
| `delegates` | **REMOVE** | One field overloads agent-as-tool, handoff, graph transition, shared-state run, and team collaboration. A typed relationship module may follow separately. |

## What ran

Each environment is independently locked because a single environment is impossible: CrewAI 1.15.18 requires `openai>=2.30,<3`, while OpenAI Agents 0.22.0 requires `openai>=3,<4`. Python 3.13 was used because CrewAI's transitive Chroma/Pydantic v1 path failed to import on Python 3.14.

| Runtime | Tested version | Native objects constructed | Runtime exercised | Full fixture strict result |
|---|---:|---|---|---|
| LangChain / LangGraph | LangChain 1.4.0; LangGraph 1.2.11 | `CompiledStateGraph`, `StructuredTool` | Parent → child agent-tool → parent | Rejected |
| CrewAI | 1.15.18 | `Agent`, `Crew`, native Skills, MCP configs | Leaf `Agent.kickoff`; native skill load | Rejected |
| LlamaIndex | core 0.14.24 | `FunctionAgent`, `AgentWorkflow`, `BasicMCPClient` | Leaf `FunctionAgent.run` | Rejected |
| Agno | 3.0.5 | `Agent`, `Team`, `Skills`, `MCPTools` | Leaf `Agent.run`; native skill load | Rejected |
| OpenAI Agents SDK | 0.22.0 | `Agent`, MCP servers, agent tools | Parent → child `Agent.as_tool` → parent | Accepted, durability unverified |
| Google ADK | 2.8.0 | `LlmAgent`, `AgentTool`, `McpToolset` | Parent → nested AgentTool → parent | Rejected |
| PydanticAI | 2.38.0 | `Agent`, `Tool`, `MCPToolset` | Parent → async adapter tool → child → parent | Accepted, durability unverified |
| Microsoft Agent Framework | 1.17.0 | `Agent`, `SkillsProvider`, MCP tools, agent tools | Parent → child `Agent.as_tool` → parent | Accepted, durability unverified |

The runtime traces are under `generated/runtime/<target>/runtime.json`; each directory also contains `test-output.txt`. Individual compatibility reports are under `generated/runtime/<target>/compatibility.json`. `generated/runtime/matrix.json` and `matrix.md` are generated from those eight reports plus the still-valid static-lowering reports for Amplifier, Claude Code, Codex, and AFM. The matrix labels evidence kind; static lowering is not presented as runtime certification. It also records hashes for every unchanged research-fixture file.

CrewAI, Agno, and LlamaIndex multi-agent objects were constructed but their team/workflow transitions were not forced with invented orchestration. The profile does not contain the task graph, process, shared-state, or routing policy those mechanisms require. That underdetermination is evidence against `delegates`, not a reason to fabricate a passing run.

## Classification matrix

This table summarizes the entry agent. Machine-readable agent-by-agent details and explanations remain authoritative.

| Target | name | description | instructions | requires | prefers | skills | durability | plugins | delegates |
|---|---|---|---|---|---|---|---|---|---|
| LangGraph | preserved | resolved | preserved | resolved | omitted | resolved | unverified | unsupported | resolved |
| CrewAI | approximated | approximated | approximated | resolved | omitted | preserved | unverified | resolved | approximated |
| LlamaIndex | preserved | preserved | preserved | resolved | omitted | resolved | unverified | unsupported | approximated |
| Agno | preserved | approximated | preserved | resolved | omitted | preserved | unverified | resolved | approximated |
| OpenAI Agents | preserved | preserved | preserved | resolved | omitted | resolved | unverified | resolved | preserved |
| Google ADK | resolved | preserved | preserved | resolved | omitted | resolved | unverified | resolved | approximated |
| PydanticAI | preserved | preserved | preserved | resolved | omitted | resolved | unverified | resolved | resolved |
| Microsoft Agent Framework | preserved | preserved | preserved | resolved | omitted | preserved | unverified | resolved | preserved |
| Amplifier (static) | preserved | preserved | preserved | resolved | resolved | unsupported | n/a | unsupported | preserved |
| Claude Code (static) | preserved | preserved | preserved | resolved | resolved | resolved | n/a | resolved | preserved |
| Codex (static) | preserved | preserved | preserved | resolved | resolved | resolved | n/a | resolved | resolved |
| AFM 0.4.0 (static) | preserved | preserved | preserved | resolved | resolved | preserved | n/a | resolved | unsupported |

`requires` combines the fixture's `reasoning` and `tool-use` rows; every runtime result is a binding attestation, not native capability proof. `prefers` abbreviates `omitted-preference` for runtime targets. The earlier static targets used a binding that selected the preferred capability, so their result is `resolved`. `durability` is the `skills.durability` finding; static targets were never executed, so it is not declared for them.

### Conformance by module

Strict outcome per module across all agents of the fixture, from `generated/runtime/matrix.md`. `accepted` means no finding in the module is `approximated` or `unsupported`; `unverified` findings do not block.

| Module | LangGraph | CrewAI | LlamaIndex | Agno | OpenAI Agents | Google ADK | PydanticAI | Microsoft |
|---|---|---|---|---|---|---|---|---|
| core | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted |
| description | accepted | rejected | accepted | rejected | accepted | accepted | accepted | accepted |
| model | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| skills | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| plugins | rejected | accepted | rejected | accepted | accepted | accepted | accepted | accepted |
| delegates | accepted | rejected | rejected | rejected | accepted | rejected | accepted | accepted |

A rejected combined fixture does not show the core is non-portable. CrewAI is the only runtime whose core is rejected, because its role, goal, and backstory prompt template changes the boundary of both name and instructions.

## Field findings

### `name` — CORE

Observed mechanisms:

- LangGraph, LlamaIndex, Agno, OpenAI Agents, PydanticAI, and Microsoft have native name fields.
- CrewAI has a role, not a stable agent identity; using the source name as role changes its semantics.
- Google ADK rejects `lead-researcher` because names must be valid Python identifiers. The adapter uses `lead_researcher` and retains an explicit source/native identity map.
- The four static targets have native identity fields.

Intersection: a stable logical identity is necessary for references, diagnostics, and package resolution. Native spelling is not portable.

Important difference: a runtime identifier may have a stricter grammar or may double as prompt content.

Recommendation: keep `name` as required metadata, define it as the package-level logical identity, and permit only deterministic, collision-checked, reversible native-name resolution. Do not claim byte-for-byte native preservation when a resolver is used. With `delegates` removed there are no intra-document references, so the name defines discovery and diagnostics, not runtime behavior.

### `description` — OPTIONAL

Observed mechanisms:

- Google ADK, LlamaIndex, OpenAI Agents, PydanticAI, and Microsoft expose native description or handoff-description metadata.
- LangGraph's compiled entry agent has no description property. The adapter keeps every description in an agent catalog in the artifact metadata, where it never enters the prompt, and a child description also becomes the tool description when the child is wrapped as a tool.
- Agno injects description into model context.
- CrewAI's closest field is `goal`, which is behavioral prompt content rather than passive selection metadata.

Intersection: a human-readable hint about what an agent does and when to select it.

Important difference: discovery metadata, routing metadata, tool description, and behavioral goal are not interchangeable. Promotion into instructions can change output.

Recommendation: retain description as optional metadata used to understand, display, discover, or select an agent. A same-named native field is not automatically preservation, and the lack of one is not automatically `unsupported`: a host that retains the description in its own catalog, registry, UI, or diagnostics and names that surface reports `resolved`. A target that can only inject it as behavioral prompt content must report `approximated`; strict mode rejects that mapping. CrewAI and Agno could reach `resolved` by keeping the description out of `goal` and the model context, which this experiment did not attempt.

### Markdown instructions — CORE

Observed mechanisms:

- LangGraph, LlamaIndex, Agno, OpenAI Agents, Google ADK, PydanticAI, Microsoft, and the static targets provide persistent instruction/system-prompt paths.
- Google ADK's string instructions perform `{state_key}` interpolation; the adapter uses a native instruction callback so arbitrary Markdown remains literal.
- Microsoft passes instructions through chat options to the client rather than inserting a `system` message itself; the nested runtime recorded the child instructions in those options.
- CrewAI embeds the body as `backstory` within a generated role/goal/backstory prompt template. The instructions run, but their boundary and authority are changed.

Intersection: persistent behavioral context applied on every invocation, distinct from ordinary task input and tool output.

Important difference: exact provider message role is not portable. Instruction authority is.

Recommendation: keep the Markdown body in the core. Define semantic preservation by persistence and authority, not by a required provider message role or byte-identical final prompt.

### `model.requires` — OPTIONAL MODULE, HOST RESOLVED

Observed mechanism in all eight runtime adapters: the profile parser exposes capability names, but the framework model objects do not provide a common, trustworthy capability contract. Every successful result came from an external binding assertion such as `tool-use: true`.

Intersection: the agent author knows what the agent needs; the deployment knows which concrete model provides it and can refuse to bind one that does not. The requirement is host resolved, not host authored.

Important differences:

- `tool-use` can sometimes be inferred from model/tool APIs, but support may depend on provider, selected model, or request mode.
- `reasoning` has no shared operational definition across the SDKs.
- Capability names, evidence, and fallback policy are deployment concerns.

Recommendation: keep `model.requires` in the profile as an optional module so deployments do not have to rediscover an agent's intrinsic needs. Declaration lives in the document; vocabulary governance lives outside it; selection and attestation live in the host binding. Reports classify a requirement `resolved` only on recorded attestation and must not imply the SDK verified it. `reasoning` should be removed or reclassified as a locally attested profile until it has a shared operational definition.

### `model.prefers` — REMOVE

Observed mechanism: all runtime experiments deliberately bound models without the preferred `vision-input` and reported `omitted-preference`. Execution behavior was unchanged, as required for a preference.

Intersection: none beyond a non-binding deployment hint.

Important difference: model selectors use incompatible vocabularies and ranking rules.

Recommendation: remove `model.prefers` from the portable agent document. Put model-selection preferences in target bindings or deployment policy, where ignoring them cannot be confused with semantic preservation.

### `skills` — OPTIONAL

Observed mechanisms:

- CrewAI, Agno, and Microsoft have native Agent Skills implementations. Tests proved metadata-only discovery and then invoked the native loader (CrewAI `LoadSkillTool`, Agno `get_skill_instructions`, Microsoft `SkillsProvider` `load_skill`). Each delivers the full body on demand as a tool result, which the Agent Skills integration guide names as dedicated tool activation. Microsoft gates `load_skill` behind approval by default; the adapter disables that gate and records it as host policy.
- Claude Code, Codex, and AFM have still-valid static Agent Skills mappings, with scope differences documented in their reports.
- LangGraph, LlamaIndex, OpenAI Agents, Google ADK, and PydanticAI have no Agent Skills concept; the adapter supplies the dedicated activation tool with the catalog in its description. That is `resolved`: the pattern is the published one, but the framework did not provide it.
- No experiment exercised context compaction or summarization, so whether activated skill content stays effective for the session is `unverified` in all eight runtimes.
- Agent Skills does not define skill isolation. The `skills` field is additive: the listed skills must be available to the agent. Whether the host also exposes ambient skills is host policy.
- Amplifier's direct static mapping remains unsupported without a runtime module.

Intersection: a catalog identified by name and description, full instructions disclosed only when activated, and resources reachable on demand.

Important differences: catalog scope, session durability under compaction, approval, resource access, and script execution. The delivery mechanism is not one of them: the integration guide treats a tool result as a conforming way to bring instructions into context.

Recommendation: retain Agent Skill references as an optional capability module graded against the Agent Skills specification and integration guide: metadata first, on-demand activation, full instructions into context, resources on demand. Native implementations are `preserved`, adapter supplied activation tools are `resolved`, eager injection is `approximated`. Session durability is a separate finding and remains `unverified` until a compaction test exists.

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

- LangGraph: no agent relationship primitive; an adapter-authored `StructuredTool` starts a fresh child graph and returns text. Graded `resolved`: it implements the draft 0.1 contract, though the framework does not provide it.
- OpenAI Agents and Microsoft: native agent-as-tool; Microsoft explicitly defaults to an independent child session.
- PydanticAI: no agent relationship primitive; an async adapter `Tool` reproduces the bounded text-in/text-out contract, graded `resolved` for the same reason as LangGraph. A first synchronous implementation failed at runtime because nested `run_sync()` is forbidden.
- Google ADK: `AgentTool` creates a child session but copies parent state and propagates child state deltas back.
- LlamaIndex: `AgentWorkflow.can_handoff_to` transfers active control through shared workflow state.
- Agno: `Team` expresses team/member collaboration.
- CrewAI: delegation is coupled to Crew tasks, context, and process.
- Codex exposes a project catalog rather than the same per-parent contract; AFM 0.4.0 has no local equivalent.

Intersection: other named agents may be available. There is no shared answer to who retains control, whether state is shared, whether the child is a tool, whether a workflow transition occurs, or what task/result contract applies.

Important difference: these mechanisms change observable behavior. Treating a handoff or shared team as a fresh child function call is not lowering; it is inventing an orchestration policy. An adapter-authored tool that implements an explicit source contract is legitimate; the problem is that one generic field cannot say which contract a target actually honors.

Recommendation: remove the generic `delegates` field from the profile because it is semantically overloaded, not because adapter implementation is illegitimate. If package composition is needed, use a non-behavioral `agents:` inventory convention or an external manifest. A future optional module may define one explicitly typed relationship such as `agent-as-tool`; draft 0.2 does not cover multi-agent orchestration.

## Conformance results

Strict construction rejects any required semantic classified `approximated` or `unsupported`; it never discards one. `omitted-preference` and `unverified` are non-blocking, and every `unverified` finding is listed in the report. Every report contains exactly one finding for every semantic declared by every source agent, and an outcome per module.

The combined draft 0.1 fixture was accepted by OpenAI Agents SDK, PydanticAI, and Microsoft Agent Framework, each with skill durability unverified. Seven of eight runtimes accept the core module. The per-module table above shows which optional module each remaining target cannot preserve: description in CrewAI and Agno, plugins in LangGraph and LlamaIndex, delegates in CrewAI, LlamaIndex, Agno, and Google ADK.

## Proposed profile changes

1. Reduce the core to `name` as required metadata plus Markdown instructions.
2. Make `description`, `model.requires`, `skills`, and `plugins` optional capability modules. A host declares which modules it implements and reports conformance per module.
3. Keep `model.requires` in the document as a host-resolved declaration; move `model.prefers`, model selection, and attestation to external target bindings.
4. Remove `delegates` from the profile because it is overloaded. Allow package inventory as a convention; leave typed relationships to a future module.
5. Extend the diagnostic vocabulary with `unverified` for properties that were not exercised. Keep `omitted-preference` for legacy reports only.
6. Require adapters to distinguish construction, activation, and execution evidence.
7. Continue to forbid in-document host extensions. Target bindings remain external.

## Limits

- Deterministic fake/model subclasses avoided paid network inference but used each framework's real agent, tool, workflow/team, and runner code paths.
- The fixture's `https://research.example.com/mcp` endpoint is illustrative and unreachable. MCP client construction was tested; a live cross-framework server handshake was not claimed.
- The four earlier targets remain static-lowering evidence only.
- No conclusion depends on generated answer quality. The experiment tests representation, authority, scope, and control flow.
- Skill activation was judged against the Agent Skills integration guide, not measured. No test exercises context compaction, so durability of activated skill content is unverified in every runtime.
- Strict acceptance or rejection of the full fixture is a construction result. No full-fixture run reached a live MCP endpoint.
