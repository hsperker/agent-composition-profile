# Agent Composition Profile evidence

**Date:** 3 September 2026

**Fixtures:** `examples/research-team/` (unchanged throughout), `examples/runtime-probes/delegation/` (delegation without the fixture's unreachable MCP endpoint), `examples/runtime-probes/plugin-activation/` (one Agent Plugin, a local MCP echo server over stdio and header gated streamable HTTP).

## Result

The candidate profile is not one portable runtime abstraction. Two fields survived as the core: a logical name and persistent agent level instructions. Description, Agent Skills, and Agent Plugins survived as optional fields with one rule: if present, a strict host preserves the field's defined semantics or rejects the profile. Model requirements survived as a concept without a vocabulary. Model preferences and generic delegation did not survive.

| Field | Status | What survived |
|---|---|---|
| `name` | **REQUIRED METADATA** | Stable logical identity for discovery, diagnostics, and packaging. A host may translate it to a native identifier only with a collision free mapping back. Not itself a runtime behavior. |
| Markdown instructions | **CORE** | Persistent agent level behavioral instructions, applied on every invocation and kept distinct from ordinary task input. |
| `description` | **OPTIONAL** | Metadata to understand, display, discover, or select the agent. Never merged into instructions. A catalog profile may require it. |
| `skills` | **OPTIONAL** | Additive Agent Skills declaration: metadata first, activation on demand. Verified: catalog and activation. Not verified: behavior under context compaction, access to bundled resources. |
| `plugins` | **OPTIONAL** | A referenced plugin contributes all its standard components; a strict host makes them available to the declaring agent or rejects. Composition is guaranteed, a stable model visible tool name is not. |
| `model.requires` | **INCUBATING** | Declared by the author, attested by the host binding. Sound as a concept; `tool-use` and `reasoning` have no standardized meaning. |
| `model.prefers` | **REMOVED** | Deployment selection policy. Belongs in the host binding. |
| `delegates` | **REMOVED** | One field for `agent-as-tool`, handoff, graph transition, shared state runs, and team collaboration. No agent inventory replaces it. |

How to read the grades. Each adapter states a grade and its reason for every field of every agent, tests assert those grades, and construction and runtime observations back them. The grades are judgments against the published Agent Skills, Agent Plugins, and MCP contracts, not measurements derived from traces. Deterministic models prove that instructions, tool calls, and results travel through the real framework code paths, not that a model behaves differently. A property that was not exercised is `unverified`, never `approximated`. Strict mode rejects `approximated` and `unsupported`, never discards a field, and lets `unverified` pass while listing it.

## What ran

Each framework has its own hash locked environment. One shared environment is impossible: CrewAI 1.15.18 needs `openai>=2.30,<3`, OpenAI Agents 0.22.0 needs `openai>=3,<4`. Python 3.13, because CrewAI's Chroma and Pydantic v1 path fails to import on 3.14.

| Runtime | Version | Native objects | Runtime path exercised | Full fixture, strict |
|---|---:|---|---|---|
| LangGraph | LangChain 1.4.0, LangGraph 1.2.11 | `CompiledStateGraph`, `StructuredTool` | parent, child agent tool, parent | rejected |
| CrewAI | 1.15.18 | `Agent`, `Crew`, native Skills, MCP configs | leaf `Agent.kickoff`, native skill load | rejected |
| LlamaIndex | core 0.14.24 | `FunctionAgent`, `AgentWorkflow`, `BasicMCPClient` | leaf `FunctionAgent.run` | rejected |
| Agno | 3.0.5 | `Agent`, `Team`, `Skills`, `MCPTools` | leaf `Agent.run`, native skill load | rejected |
| OpenAI Agents SDK | 0.22.0 | `Agent`, MCP servers, agent tools | parent, child `Agent.as_tool`, parent | accepted, skills unverified |
| Google ADK | 2.8.0 | `LlmAgent`, `AgentTool`, `McpToolset` | parent, nested `AgentTool`, parent | rejected |
| PydanticAI | 2.38.0 | `Agent`, `Tool`, `MCPToolset` | parent, async adapter tool, child, parent | accepted, skills unverified |
| Microsoft Agent Framework | 1.17.0 | `Agent`, `SkillsProvider`, MCP tools, agent tools | parent, child `Agent.as_tool`, parent | accepted, skills unverified |

Per target: `generated/runtime/<target>/compatibility.json`, `runtime.json`, `plugin-activation.json`, `test-output.txt`. `generated/runtime/matrix.md` merges the eight runtime reports with the four static lowering reports and labels which is which. CrewAI, Agno, and LlamaIndex team and workflow objects were constructed but their transitions were not forced: the profile carries no task graph, process, or routing policy, and inventing one would be evidence for nothing.

## Grades

Entry agent only. The JSON reports hold every agent and every reason.

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

`requires` covers the fixture's `reasoning` and `tool-use`; every runtime result is a binding attestation, not native proof. `prefers` is `omitted-preference` at runtime; the static bindings selected the preferred capability. `durability` and `resources` are `skills.durability` and `skills.resources`; static targets never ran, so neither applies.

Strict outcome per field group, all agents:

| Field | LangGraph | CrewAI | LlamaIndex | Agno | OpenAI Agents | Google ADK | PydanticAI | Microsoft |
|---|---|---|---|---|---|---|---|---|
| core | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted |
| description | accepted | rejected | accepted | rejected | accepted | accepted | accepted | accepted |
| model | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| skills | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| plugins | rejected | accepted | rejected | accepted | accepted | accepted | accepted | accepted |
| delegates | accepted | rejected | rejected | rejected | accepted | rejected | accepted | accepted |

A rejected combined fixture says which field a target cannot preserve, not that the core is unportable. CrewAI is the one core rejection. Its role, goal, and backstory template fuses name, description, and instructions, and its template override drops role and goal only by collapsing the prompt into a single user message. That is a different agent abstraction, and the core should not be bent to pass it.

## Findings by field

### `name`

Six runtimes have a native name field. CrewAI has a role, which is prompt content, not identity. Google ADK requires Python identifiers, so `lead-researcher` becomes `lead_researcher` with an explicit map back. All four static targets have identity fields.

The portable part is a stable logical identity for discovery, diagnostics, and packaging. Native spelling is not portable, and a native identifier may double as prompt content. With `delegates` gone the document has no internal references, so the name defines nothing at runtime. A host may translate it only with a collision free mapping back, graded `resolved` rather than `preserved`.

### `description`

Google ADK, LlamaIndex, OpenAI Agents, PydanticAI, and Microsoft have native description or handoff metadata. LangGraph's compiled agent has none, so the adapter keeps descriptions in a catalog in the artifact metadata, never in the prompt, and children wrapped as tools carry theirs as the tool description. Agno injects the description into model context. CrewAI's nearest field is `goal`, which is behavioral.

Discovery metadata, routing metadata, tool description, and behavioral goal are not interchangeable; promotion into instructions can change output. A same named native field is not preservation, and the lack of one is not `unsupported`: a host that keeps the description in a catalog, registry, UI, or diagnostics and says where reports `resolved`. Injection into prompt content is `approximated` and strict mode rejects it. CrewAI and Agno could reach `resolved` by keeping the description out of the prompt; this experiment did not try.

### Markdown instructions

Seven runtimes and all static targets have a persistent instruction path. Google ADK interpolates `{state_key}` in string instructions, so the adapter passes a callback to keep Markdown literal. Microsoft passes instructions through chat options rather than writing a system message itself.

CrewAI embeds the body as `backstory` inside its generated role, goal, backstory template, so the instructions are no longer separate from role and goal text. Custom templates (`system_template="{backstory}"`, `prompt_template="{input}"`) remove role and goal, but CrewAI's prompt builder returns one combined prompt for any template override and sends it as a single user message fused with the task. The test `test_custom_templates_drop_role_and_goal_but_merge_instructions_into_the_user_turn` records both shapes. Neither path yields persistent instructions distinct from task input, so `approximated` stands.

Preservation means persistence and separation from ordinary task input. It does not mean a particular provider role or a byte identical prompt.

### `model.requires`

No SDK exposes a common, trustworthy capability contract. Every `resolved` result came from a binding assertion such as `tool-use: true`. `tool-use` can sometimes be inferred from model and tool APIs but depends on provider, model, and request mode. `reasoning` has no shared operational meaning.

The author knows what the agent needs; the deployment knows which model provides it and can refuse one that does not. The requirement is host resolved, not host authored, so it stays in the document. But a requirement is interoperable only when its name has a standardized meaning, and none does yet. Incubating, not in the first normative proposal. Reports grade a requirement `resolved` only on recorded attestation and never imply the SDK verified it.

### `model.prefers`

Every runtime bound a model without the preferred `vision-input`, reported `omitted-preference`, and behaved identically. Selectors use incompatible vocabularies and ranking rules. Preferences are deployment policy and belong in the host binding.

### `skills`

CrewAI, Agno, and Microsoft implement Agent Skills natively. Tests confirmed metadata only discovery, then invoked the native loader (`LoadSkillTool`, `get_skill_instructions`, `SkillsProvider.load_skill`). Each returns the full body on demand as a tool result, the dedicated tool activation the Agent Skills integration guide describes, so `preserved`. Microsoft gates loading behind approval by default; the adapter disables it and records that as host policy. LangGraph, LlamaIndex, OpenAI Agents, Google ADK, and PydanticAI have no skills concept; the adapter supplies the activation tool with the catalog in its description, so `resolved`. Claude Code, Codex, and AFM have static mappings with documented scope differences. Amplifier has none without a runtime module.

Not exercised, and therefore `unverified` everywhere: whether activated content survives context compaction, and whether bundled references, scripts, and assets are reachable on demand, since the fixture skills bundle none. Agent Skills does not define skill isolation, so `skills` is additive: the listed skills must be available to the agent, and ambient skills are host policy.

### `plugins`

Six runtimes construct native MCP clients from the plugin's `mcp.json` at build time. LangGraph and LlamaIndex cannot attach tools until a handshake succeeds; against the research fixture's unreachable endpoint they report `unsupported` rather than invent tools. Construction proves representability, not activation, so the research fixture keeps `plugins.activation` unverified and a separate probe supplies the live evidence.

The probe plugin declares a stdio server (`command: python`, `${PLUGIN_ROOT}` in `args` and `cwd`, a custom `env` entry) and a streamable HTTP server that answers 401 without the configured header. One echo server script runs under MCP SDK 1.x and 2.x, because the environments pin three `mcp` releases. A deterministic model calls every echo tool once. The echo result reports working directory, whether `PLUGIN_ROOT` and `PLUGIN_DATA` arrived, and which server answered.

| Target | stdio | HTTP with header | stdio cwd honored | stdio env honored | Tool naming |
|---|---|---|---|---|---|
| LangGraph | activated | activated | yes | yes | as published |
| CrewAI | activated | activated | no | yes | derived from command or URL, hashed when long |
| LlamaIndex | activated | activated | no | yes | as published |
| Agno | activated | activated | yes | yes | as published |
| OpenAI Agents | activated | activated | yes | yes | as published |
| Google ADK | activated | activated | yes | yes | `<server>_<tool>` |
| PydanticAI | activated | activated | yes | yes | as published |
| Microsoft Agent Framework | activated | activated | yes | yes | `<server>_<tool>` |

What the probe showed:

- **Agent Plugins §7.2.1 and §9 are the host's job.** No SDK defaults `cwd` to the plugin root, expands `${PLUGIN_ROOT}`, or provides the reserved variables. The shared `effective_server_config` helper does, and every stdio server then saw both.
- **Native MCP support is not Agent Plugins support.** CrewAI's `MCPServerStdio` and LlamaIndex's `BasicMCPClient` cannot set a working directory. Since the plugin root is the required default, both adapters grade every stdio server `unsupported`, and strict mode rejects the probe fixture for both. Their `resolved` grade in the research fixture is consistent: that plugin has only an HTTP server. AFM 0.4.0 loses every stdio server for the same reason.
- **Headers survived everywhere.** The 401 gate never fired.
- **Tool names are not portable.** ADK and Microsoft prefix with the server name. CrewAI names tools after the command or URL and truncates long names to a hash, so the model saw `python_users_..._98b36a1f` for `echo_stdio`. Agent Plugins leaves presentation to the host. A plugin reference therefore guarantees composition, not a tool identifier an instruction can rely on. "Always call `echo_stdio`" is unsafe in a portable profile.
- **Server attribution is not portable.** CrewAI exposes no mapping from a discovered tool to its server; the probe attributes by payload content.
- **Lifecycle ownership differs.** OpenAI Agents needs an explicit `connect()`. Microsoft and PydanticAI connect when the agent enters its async context. Agno connects inside `arun`. ADK connects on first tool listing. CrewAI connects inside `kickoff`. LangGraph opens a session per call. LlamaIndex binds its HTTP client to the first event loop that uses it.

Not tested: two servers with the same tool name, SSE, OAuth, and failure reporting per §7.2.2, which the adapters implement but no server triggered.

A referenced plugin contributes all its standard components; a strict host makes them available to the declaring agent, working directory default included, or rejects. This is a profile composition rule, not a change to Agent Plugins conformance, which allows clients with partial component support. Availability is not isolation; scoping stays with the host.

### `delegates`

The eight runtimes use six mechanisms. OpenAI Agents and Microsoft: native agent as tool, Microsoft in an isolated child session. LangGraph and PydanticAI: no relationship primitive, so an adapter tool implements the draft 0.1 contract of fresh child, task in, text out, control returns; graded `resolved`. Google ADK `AgentTool`: a child session that copies parent state and propagates deltas back. LlamaIndex `can_handoff_to`: transfer of control through shared workflow state. Agno `Team`: member collaboration. CrewAI: delegation bound to Crew tasks, context, and process. Codex exposes a project catalog; AFM has no local equivalent.

The only shared meaning is that other agents exist. Who keeps control, whether state is shared, whether the child is a tool, and what the result contract is all differ, and lowering one mechanism into another invents orchestration policy. The field is removed because it is overloaded, not because adapter tools are illegitimate. No `agents:` inventory replaces it: a profile describes one agent, a package may hold several, orchestration relates them. A typed relationship such as `agent-as-tool` could become a future optional field.

## Limits

- Deterministic model doubles avoided paid inference. They ran through each framework's real agent, tool, team or workflow, and runner code, but prove nothing about model behavior.
- The research fixture's `https://research.example.com/mcp` endpoint is unreachable by design. Live activation comes only from the probe, against a local echo server, not a shared reference server.
- The four static targets were never executed.
- Skill grades follow the Agent Skills integration guide. Compaction and bundled resources were not exercised.
- The combined fixture's strict outcome is a construction result. The probe fixture has no skills or delegates.
- The probe did not cover SSE, OAuth, colliding tool names, or activation failure reporting.
