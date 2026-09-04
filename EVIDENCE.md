# Agent Composition Profile runtime evidence

**Experiment date:** 3 September 2026

**Portable fixture:** `examples/research-team/` (unchanged)

**Additional probes:** `examples/runtime-probes/delegation/` (isolates delegation from the fixture's intentionally unreachable MCP endpoint) and `examples/runtime-probes/plugin-activation/` (one Agent Plugin with a local deterministic MCP echo server over stdio and header-gated streamable HTTP)

## Result

The proposed profile is not one coherent portable runtime abstraction.

Two semantics survived as a convincing core: a logical agent identity as required metadata and persistent behavioral instructions as the one core behavioral semantic. Description, Agent Skills, and Agent Plugins are optional fields with one rule: if present, a strict host must preserve their defined semantics or reject the profile. Model requirements are declared by the agent author and resolved by the host, but without a standardized capability vocabulary they remain incubating. The generic `delegates` field overloads several incompatible mechanisms and should leave the profile.

This is not a majority vote. The recommendations below use the semantic intersection actually observed. A framework accepting similarly named constructor arguments does not count as preservation.

The classifications are recorded reviewer judgments about each native mechanism, graded against the published Agent Skills, Agent Plugins, and MCP contracts. Each adapter states its grade and rationale explicitly, the tests assert those grades, and the construction and runtime observations back them. The grades are not derived from the traces by measurement. The runtime runs use scripted deterministic models, so they prove that instructions, tool calls, and returns travel through the real framework code paths, not that any model behaves differently as a result. A property that was not exercised is recorded as `unverified`, never as `approximated`. Read the matrix as a structured, reproducible assessment, not as an instrument reading.

| Source semantic | Recommendation | Narrow semantic that survived |
|---|---|---|
| `name` | **REQUIRED METADATA** | Stable logical identity for discovery, diagnostics, and packaging. A host may translate it to a target-specific identifier only if it retains a collision-free mapping back to the logical name. Not itself a runtime behavior. |
| Markdown instructions | **CORE** | Persistent agent-level behavioral instructions applied on every invocation and kept distinct from ordinary task input. |
| `description` | **OPTIONAL** | Metadata to understand, display, discover, or select the agent; it must not be merged into behavioral instructions. A catalog profile may require it. |
| `model.requires` | **INCUBATING** | Declared by the agent author, attested by the host binding. Sound as a concept, but `tool-use` and `reasoning` have no standardized meaning yet. |
| `model.prefers` | **REMOVE** | Non-binding deployment selection policy; belongs in the host binding. |
| `skills` | **OPTIONAL** | Additive Agent Skills declaration with metadata-first, on-demand activation per the Agent Skills integration guide. The experiment verified catalog disclosure and activation; it did not verify behavior under context compaction or access to bundled resources. |
| `plugins` | **OPTIONAL** | A referenced Agent Plugin contributes all standard components it contains; a strict host makes them available to the declaring agent or rejects the profile. Composition is guaranteed; a stable model-visible tool identifier is not. |
| `delegates` | **REMOVE** | One field overloads agent-as-tool, handoff, graph transition, shared-state run, and team collaboration. No agent inventory replaces it; packaging and orchestration are separate concerns. |

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

| Target | name | description | instructions | requires | prefers | skills | durability | resources | plugins | delegates |
|---|---|---|---|---|---|---|---|---|---|---|
| LangGraph | preserved | resolved | preserved | resolved | omitted | resolved | unverified | unverified | unsupported | resolved |
| CrewAI | approximated | approximated | approximated | resolved | omitted | preserved | unverified | unverified | resolved | approximated |
| LlamaIndex | preserved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | unsupported | approximated |
| Agno | preserved | approximated | preserved | resolved | omitted | preserved | unverified | unverified | resolved | approximated |
| OpenAI Agents | preserved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | resolved | preserved |
| Google ADK | resolved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | resolved | approximated |
| PydanticAI | preserved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | resolved | resolved |
| Microsoft Agent Framework | preserved | preserved | preserved | resolved | omitted | preserved | unverified | unverified | resolved | preserved |
| Amplifier (static) | preserved | preserved | preserved | resolved | resolved | unsupported | n/a | n/a | unsupported | preserved |
| Claude Code (static) | preserved | preserved | preserved | resolved | resolved | resolved | n/a | n/a | resolved | preserved |
| Codex (static) | preserved | preserved | preserved | resolved | resolved | resolved | n/a | n/a | resolved | resolved |
| AFM 0.4.0 (static) | preserved | preserved | preserved | resolved | resolved | preserved | n/a | n/a | resolved | unsupported |

`requires` combines the fixture's `reasoning` and `tool-use` rows; every runtime result is a binding attestation, not native capability proof. `prefers` abbreviates `omitted-preference` for runtime targets. The earlier static targets used a binding that selected the preferred capability, so their result is `resolved`. `durability` and `resources` are the `skills.durability` and `skills.resources` findings; static targets were never executed, so neither is declared for them.

### Conformance by field

Strict outcome for the required core and for each optional field, across all agents of the fixture, from `generated/runtime/matrix.md` (the JSON key is `modules`). `accepted` means no finding in the group is `approximated` or `unsupported`; `unverified` findings do not block.

| Field | LangGraph | CrewAI | LlamaIndex | Agno | OpenAI Agents | Google ADK | PydanticAI | Microsoft |
|---|---|---|---|---|---|---|---|---|
| core | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted |
| description | accepted | rejected | accepted | rejected | accepted | accepted | accepted | accepted |
| model | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| skills | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| plugins | rejected | accepted | rejected | accepted | accepted | accepted | accepted | accepted |
| delegates | accepted | rejected | rejected | rejected | accepted | rejected | accepted | accepted |

A rejected combined fixture does not show the core is non-portable. CrewAI is the only runtime whose core is rejected, because its role, goal, and backstory prompt template changes the boundary of both name and instructions, and its template override trades that for a single user message with no persistent system context. That is a genuinely different agent abstraction, and the portable core should not be contorted to make it pass.

## Field findings

### `name` — CORE

Observed mechanisms:

- LangGraph, LlamaIndex, Agno, OpenAI Agents, PydanticAI, and Microsoft have native name fields.
- CrewAI has a role, not a stable agent identity; using the source name as role changes its semantics. CrewAI's custom `system_template` and `prompt_template` were probed as a route around this: they do remove role and goal from the prompt, but CrewAI then builds one combined prompt with no system message, so the mechanism does not restore a clean identity plus instructions split.
- Google ADK rejects `lead-researcher` because names must be valid Python identifiers. The adapter uses `lead_researcher` and retains an explicit source/native identity map.
- The four static targets have native identity fields.

Intersection: a stable logical identity is necessary for references, diagnostics, and package resolution. Native spelling is not portable.

Important difference: a runtime identifier may have a stricter grammar or may double as prompt content.

Recommendation: keep `name` as required metadata and define it as the package-level logical identity. A host may translate it to a target-specific identifier only if it retains a collision-free mapping back to the logical name. Do not claim byte-for-byte native preservation when a translation is used. With `delegates` removed there are no intra-document references, so the name defines discovery and diagnostics, not runtime behavior.

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
- CrewAI embeds the body as `backstory` within a generated role/goal/backstory prompt template. The instructions run, but they are no longer separate from role and goal text. With custom templates (`system_template="{backstory}"`, `prompt_template="{input}"`) role and goal disappear, but CrewAI's prompt builder returns a single prompt for any template override and the executor sends it as one user message fused with the task text. The test `test_custom_templates_drop_role_and_goal_but_merge_instructions_into_the_user_turn` records both message shapes. Neither path yields persistent context distinct from task input, so the `approximated` grade stands.

Intersection: persistent behavioral context applied on every invocation, distinct from ordinary task input and tool output.

Important difference: exact provider message role is not portable. Persistence and separation from task input are.

Recommendation: keep the Markdown body in the core. Define semantic preservation by persistence and separation from ordinary task input, not by a required provider message role or byte-identical final prompt.

### `model.requires` — INCUBATING, HOST RESOLVED

Observed mechanism in all eight runtime adapters: the profile parser exposes capability names, but the framework model objects do not provide a common, trustworthy capability contract. Every successful result came from an external binding assertion such as `tool-use: true`.

Intersection: the agent author knows what the agent needs; the deployment knows which concrete model provides it and can refuse to bind one that does not. The requirement is host resolved, not host authored.

Important differences:

- `tool-use` can sometimes be inferred from model/tool APIs, but support may depend on provider, selected model, or request mode.
- `reasoning` has no shared operational definition across the SDKs.
- Capability names, evidence, and fallback policy are deployment concerns.

Recommendation: keep `model.requires` as an incubating field so deployments do not have to rediscover an agent's intrinsic needs. Declaration lives in the document; vocabulary governance lives outside it; selection and attestation live in the host binding. Reports classify a requirement `resolved` only on recorded attestation and must not imply the SDK verified it. The evidence supports the concept, not a vocabulary: a requirement is interoperable only when its name has a standardized meaning, and `reasoning` clearly does not. Do not force the field into the first normative proposal.

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
- The fixture skills bundle no references, scripts, or assets, so on-demand resource access, which Agent Skills also requires, is `unverified` in all eight runtimes.
- Agent Skills does not define skill isolation. The `skills` field is additive: the listed skills must be available to the agent. Whether the host also exposes ambient skills is host policy.
- Amplifier's direct static mapping remains unsupported without a runtime module.

Intersection: a catalog identified by name and description, full instructions disclosed only when activated, and resources reachable on demand.

Important differences: catalog scope, session durability under compaction, approval, resource access, and script execution. The delivery mechanism is not one of them: the integration guide treats a tool result as a conforming way to bring instructions into context.

Recommendation: retain Agent Skill references as an optional field graded against the Agent Skills specification and integration guide: metadata first, on-demand activation, full instructions into context, resources on demand. Native implementations are `preserved`, adapter supplied activation tools are `resolved`, eager injection is `approximated`. Session durability and resource access are separate findings and remain `unverified` until a compaction test and a fixture skill with bundled resources exist. Only catalog and activation were tested; complete Agent Skills preservation is not claimed.

### `plugins` — OPTIONAL

Observed mechanisms:

- CrewAI, Agno, OpenAI Agents, Google ADK, PydanticAI, and Microsoft construct native MCP clients/toolsets from the Agent Plugin MCP server and attach them to the declaring agent.
- LangGraph and LlamaIndex can construct clients, but cannot attach tools to an agent until a handshake succeeds. Against the research fixture's unreachable endpoint they report unsupported rather than inventing tools; against the live probe they attach tools through langchain-mcp-adapters and McpToolSpec respectively.
- Static Claude, Codex, and AFM mappings resolve supported plugin components; Amplifier still needs a runtime shim.
- All eight runtimes activated the live probe plugin end to end on both transports. See the activation table below.

Intersection: an Agent Plugin reference is a required package dependency whose supported components are made available to the declaring agent, and every tested runtime's native MCP client can take the plugin's `mcp.json` entry through handshake, discovery, and invocation. Whether the same components are also visible elsewhere is a host decision; the profile promises availability, not isolation.

Important differences: the plugin wrapper disappears after expansion; MCP connection ownership, activation timing, working directory, tool naming, approvals, and tool catalog scope vary. Construction proves representability, not endpoint availability, which is why the research fixture keeps `plugins.activation` unverified and the live probe is reported separately.

#### Plugin activation probe

The probe fixture declares one plugin whose `mcp.json` has a stdio server (`command: python`, `${PLUGIN_ROOT}` in `args` and `cwd`, a custom `env` entry) and a streamable HTTP server that answers 401 without the configured header. The same echo server script runs under MCP SDK 1.x and 2.x, because the eight environments pin three different `mcp` releases. A deterministic model calls every echo tool once; the echo result reports the working directory, whether `PLUGIN_ROOT` and `PLUGIN_DATA` were provided, and which server answered. Per target results are in `generated/runtime/<target>/plugin-activation.json`, summarized in `generated/runtime/matrix.md`.

| Target | stdio | streamable HTTP with header | stdio cwd honored | stdio env honored | Tool naming |
|---|---|---|---|---|---|
| LangGraph | activated | activated | yes | yes | tool name as published |
| CrewAI | activated | activated | no | yes | derived from command or URL, hashed when long |
| LlamaIndex | activated | activated | no | yes | tool name as published |
| Agno | activated | activated | yes | yes | tool name as published |
| OpenAI Agents | activated | activated | yes | yes | tool name as published |
| Google ADK | activated | activated | yes | yes | `<server>_<tool>` |
| PydanticAI | activated | activated | yes | yes | tool name as published |
| Microsoft Agent Framework | activated | activated | yes | yes | `<server>_<tool>` |

Findings from the probe:

- Agent Plugins §9 is the adapter's job, not the SDK's. No SDK expands `${PLUGIN_ROOT}` or provides `PLUGIN_ROOT` and `PLUGIN_DATA`; the shared `effective_server_config` helper does, and every stdio server then saw both variables.
- `cwd` is lost in two SDKs. CrewAI's `MCPServerStdio` and LlamaIndex's `BasicMCPClient` have no working directory parameter, so their servers ran in the inherited directory. Agent Plugins §7.2.1 makes the plugin root the required default when `cwd` is omitted, so every stdio server needs it; both adapters therefore grade any stdio server `unsupported`, and strict mode rejects the activation fixture for both. Their `resolved` grade in the research fixture is not a contradiction: that plugin declares only a streamable HTTP server, which neither SDK mishandles. Native MCP support is not Agent Plugins support. The same rule makes AFM 0.4.0 lose every stdio server.
- Headers survived everywhere. All eight clients sent the configured header; the 401 gate never fired.
- Tool naming is not portable. Google ADK and Microsoft prefix tools with the server name. CrewAI names tools after the server command or URL, not the Agent Plugins server name, and truncates long sanitized names to a hash, so the model saw `python_users_..._98b36a1f` for `echo_stdio`. Agent Plugins delegates wire behavior to MCP and does not standardize how a host presents tools to a model. Consequently a plugin reference guarantees capability composition, not a stable model-visible tool identifier. A portable instruction such as "always call `echo_stdio` before answering" is unsafe, because another host may expose the tool as `echostdio_echo_stdio` or a hash. Portable instructions cannot rely on a target-native tool name unless another standard supplies a stable logical reference.
- Server attribution is not portable. CrewAI exposes no mapping from a discovered tool back to the configured server; the probe attributes results by payload content instead.
- Lifecycle ownership differs. OpenAI Agents needs an explicit `connect()`; Microsoft and PydanticAI connect when the agent enters its async context; Agno connects inside `arun` and releases in the same task; ADK connects on first tool listing; CrewAI connects inside `kickoff`; LangGraph opens a session per tool call; LlamaIndex binds its HTTP client to the first event loop that uses it.
- Two servers exposing the same tool name were not tested. Namespacing across servers is client defined and remains an open question.
- Activation failure reporting per Agent Plugins §7.2.2 is implemented in the adapters but was not exercised, because no server failed.

Recommendation: retain plugin references as optional composition. A referenced Agent Plugin contributes all standard components it contains; a strict host must make those components available to the declaring agent, including the §7.2.1 working directory default, or reject the profile. This is an Agent Profile composition rule, not a change to Agent Plugins conformance, which permits clients with partial component-type support. Runtime activation failures remain invocation failures. The profile must not standardize plugin lifecycle, tool naming, or scoping beyond what Agent Plugins and MCP already define. Hosts must implement Agent Plugins §7.2.1 and §9 themselves, and the profile must state that tool names seen by the model are not portable.

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

Recommendation: remove the generic `delegates` field from the profile because it is semantically overloaded, not because adapter implementation is illegitimate. Do not add an `agents:` inventory either: an Agent Profile describes one agent, a package may contain several, and orchestration defines their relationships. A future optional field may define one explicitly typed relationship such as `agent-as-tool`; draft 0.2 does not cover multi-agent orchestration.

## Conformance results

Strict construction rejects any required semantic classified `approximated` or `unsupported`; it never discards one. `omitted-preference` and `unverified` are non-blocking, and every `unverified` finding is listed in the report. Every report contains exactly one finding for every semantic declared by every source agent, and an outcome for the core and for each optional field.

The combined draft 0.1 fixture was accepted by OpenAI Agents SDK, PydanticAI, and Microsoft Agent Framework, each with skill durability and resource access unverified. Seven of eight runtimes accept the required core. The table above shows which optional field each remaining target cannot preserve: description in CrewAI and Agno, plugins in LangGraph and LlamaIndex, delegates in CrewAI, LlamaIndex, Agno, and Google ADK.

## Proposed profile changes

1. Reduce the core to `name` as required metadata plus Markdown instructions.
2. Make `description`, `skills`, and `plugins` optional fields with one rule: if present, a strict host preserves their defined semantics or rejects the profile. Report conformance for the core and for each optional field.
3. Carry `model.requires` as an incubating host-resolved declaration until a capability vocabulary is standardized; move `model.prefers`, model selection, and attestation to external target bindings.
4. Remove `delegates` from the profile because it is overloaded. Add no agent inventory; leave packaging and orchestration to their own efforts.
5. Extend the diagnostic vocabulary with `unverified` for properties that were not exercised. Keep `omitted-preference` for legacy reports only.
6. Require adapters to distinguish construction, activation, and execution evidence, and hosts to implement Agent Plugins §9 placeholder expansion and reserved variables.
7. Continue to forbid in-document host extensions. Target bindings remain external.

## Limits

- Deterministic fake/model subclasses avoided paid network inference but used each framework's real agent, tool, workflow/team, and runner code paths.
- The research fixture's `https://research.example.com/mcp` endpoint is illustrative and unreachable, so its `plugins.activation` finding stays unverified. Live activation was exercised only through the separate plugin-activation probe, against a local echo server rather than a shared reference server.
- The four earlier targets remain static-lowering evidence only.
- No conclusion depends on generated answer quality. The experiment tests representation, persistence, separation from task input, scope, and control flow.
- Skill activation was judged against the Agent Skills integration guide, not measured. No test exercises context compaction or bundled resources, so durability and resource access are unverified in every runtime.
- Strict acceptance or rejection of the full fixture is a construction result. No full-fixture run reached a live MCP endpoint; the activation probe used a two-server fixture with no skills or delegates.
- The activation probe did not test SSE, OAuth, two servers with colliding tool names, or activation failure reporting.
