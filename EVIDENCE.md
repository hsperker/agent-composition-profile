# Agent Profile evidence

**Date:** 3 September 2026

**Fixtures:** `examples/research-team/` (unchanged throughout; it uses the draft 0.1 spelling `delegates`, which the loader accepts as an alias), `examples/runtime-probes/delegation/` (a subagent call without the fixture's unreachable MCP endpoint), `examples/runtime-probes/plugin-activation/` (one Agent Plugin, a local MCP echo server over stdio and header gated streamable HTTP).

## Result

The question is how much of a candidate Agent Profile lowers unchanged into the tools people run agents in. Products are the primary dimension because they are where ownership is tested; frameworks are the check on the semantics. Product evidence is static for four products (files generated and verified) and executed for Claude Code and OpenCode, which ran headless against scripted model endpoints; framework evidence is executed with deterministic models.

The candidate profile is not one portable runtime abstraction. Two fields survived as the core: a logical name and persistent agent level instructions. Description, Agent Skills, and Agent Plugins survived as optional fields with one rule: if present, a strict host preserves the field's defined semantics or rejects the profile. Model requirements survived as a concept without a vocabulary. Model preferences did not survive. Generic delegation did not survive as one field, but one of the mechanisms it hid, an allowlisted subagent invoked as a bounded task that returns a result, did, and it survives more cleanly among products than among frameworks.

| Field | Status | What survived |
|---|---|---|
| `name` | **REQUIRED METADATA** | Stable logical identity for discovery, diagnostics, and packaging. A host may translate it to a native identifier only with a collision free mapping back. Not itself a runtime behavior. |
| Markdown instructions | **CORE** | Persistent agent level behavioral instructions, applied on every invocation and kept distinct from ordinary task input. |
| `description` | **OPTIONAL** | Metadata to understand, display, discover, or select the agent. Never merged into instructions. A catalog profile may require it. |
| `skills` | **OPTIONAL** | Additive Agent Skills declaration: metadata first, activation on demand. Verified: catalog and activation. Not verified: behavior under context compaction, access to bundled resources. |
| `plugins` | **OPTIONAL** | A referenced plugin contributes all its standard components; a strict host makes them available to the declaring agent or rejects. Composition is guaranteed, a stable model visible tool name is not. |
| `model.requires` | **INCUBATING** | Declared by the author, attested by the host binding. Sound as a concept; `tool-use` and `reasoning` have no standardized meaning. |
| `model.prefers` | **REMOVED** | Deployment selection policy. Belongs in the host binding. |
| `subagents` | **OPTIONAL** | Agents this agent may invoke as bounded tasks: own instructions, task in, result out, caller keeps control. Additive; nesting and child visibility are host policy. Replaces the generic `delegates`, which hid handoff, graph transition, shared state runs, and team collaboration behind one word. |

How to read the grades. Each adapter states a grade and its reason for every field of every agent, tests assert those grades, and construction and runtime observations back them. The grades are judgments against the published Agent Skills, Agent Plugins, and MCP contracts, not measurements derived from traces. Deterministic models prove that instructions, tool calls, and results travel through the real framework code paths, not that a model behaves differently. A property that was not exercised is `unverified`, never `approximated`. Strict mode rejects `approximated` and `unsupported`, never discards a field, and lets `unverified` pass while listing it.

## What ran

Products, static lowering by the reference compiler. A product qualifies when it reads agent definitions from files the customer controls.

| Product | Lowered to | Evidence |
|---|---|---|
| Claude Code 2.1.277 | `.claude/agents/*.md`, `.claude/skills/`, per agent `mcpServers`, `Agent(...)` subagent allowlist | generated files run headless against a scripted Anthropic endpoint; see the product probe below |
| Codex | `.codex/agents/*.toml`, `.codex/config.toml`, `.agents/skills/` | files generated, parsed, checked; not executed |
| GitHub Copilot | `.github/agents/*.agent.md` with `agents` allowlist and cloud `mcp-servers`, `.github/skills/`, `.vscode/mcp.json` | files generated, parsed, checked; not executed |
| OpenCode 1.18.32 and 2.0.14 | `.opencode/agent/*.md` with `permission.task` allowlist, `.opencode/skills/`, `opencode.json` `mcp` | generated files run headless against a scripted OpenAI compatible endpoint on both major versions; see the product probe below |
| Amplifier | bundle and agent Markdown | files generated; no skills or plugin path |
| WSO2 AFM 0.4.0 | `*.afm.md`, local skills, `tools.mcp` | files generated; no subagent relation, no stdio `cwd` |

Frameworks, executed. Each has its own hash locked environment. One shared environment is impossible: CrewAI 1.15.18 needs `openai>=2.30,<3`, OpenAI Agents 0.22.0 needs `openai>=3,<4`. Python 3.13, because CrewAI's Chroma and Pydantic v1 path fails to import on 3.14.

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

Per framework: `generated/runtime/<target>/compatibility.json`, `runtime.json`, `plugin-activation.json`, `test-output.txt`. Per probed product: `generated/products/<product>/probe-<fixture>.json`. `generated/runtime/matrix.md` merges the eight framework reports with the four product reports and labels each row `runtime` or `product-static`. CrewAI, Agno, and LlamaIndex team and workflow objects were constructed but their transitions were not forced: the profile carries no task graph, process, or routing policy, and inventing one would be evidence for nothing.

## Grades

Entry agent only. The JSON reports hold every agent and every reason.

| Target | name | description | instructions | requires | prefers | skills | durability | resources | plugins | subagents |
|---|---|---|---|---|---|---|---|---|---|---|
| LangGraph | preserved | resolved | preserved | resolved | omitted | resolved | unverified | unverified | unsupported | resolved |
| CrewAI | approximated | approximated | approximated | resolved | omitted | preserved | unverified | unverified | resolved | approximated |
| LlamaIndex | preserved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | unsupported | approximated |
| Agno | preserved | approximated | preserved | resolved | omitted | preserved | unverified | unverified | resolved | approximated |
| OpenAI Agents | preserved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | resolved | preserved |
| Google ADK | resolved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | resolved | approximated |
| PydanticAI | preserved | preserved | preserved | resolved | omitted | resolved | unverified | unverified | resolved | resolved |
| Microsoft Agent Framework | preserved | preserved | preserved | resolved | omitted | preserved | unverified | unverified | resolved | preserved |
| Amplifier (product, static) | preserved | preserved | preserved | resolved | resolved | unsupported | n/a | n/a | unsupported | preserved |
| Claude Code (product, static) | preserved | preserved | preserved | resolved | resolved | resolved | n/a | n/a | resolved | preserved |
| Codex (product, static) | preserved | preserved | preserved | resolved | resolved | resolved | n/a | n/a | resolved | resolved |
| Copilot (product, static) | preserved | preserved | preserved | resolved | resolved | resolved | n/a | n/a | resolved | preserved |
| OpenCode (product, static) | resolved | preserved | preserved | resolved | resolved | resolved | n/a | n/a | resolved | preserved |
| AFM 0.4.0 (product, static) | preserved | preserved | preserved | resolved | resolved | preserved | n/a | n/a | resolved | unsupported |

`requires` covers the fixture's `reasoning` and `tool-use`; every runtime result is a binding attestation, not native proof. `prefers` is `omitted-preference` at runtime; the static bindings selected the preferred capability. `durability` and `resources` are `skills.durability` and `skills.resources`; product targets were not executed, so neither applies.

#### Product probe: Claude Code

`scripts/verify-products.sh` compiles a fixture with the claude-code target into a temporary project, points `claude -p --agent <entry>` at a local server that speaks the Anthropic Messages API and answers from a script, and records every request the model would have seen. The user's own Claude configuration is untouched: the probe uses a fresh config directory in which only the temporary project is marked trusted. Two fixtures ran, the research team and the plugin activation probe.

| Checked | Result |
|---|---|
| Entry instructions in the system prompt | yes, on every request |
| Skills advertised before activation | names and descriptions in a system reminder message; the body absent |
| Skill activation | `Skill` tool call, then the full `SKILL.md` body injected as a user text block |
| Skill body persists | present in every later request of the session |
| Subagent call | `Agent` tool with the listed type; the child ran with its own system prompt and without an `Agent` tool of its own |
| Subagent result | returned to the caller as a later turn; Claude Code runs subagents asynchronously |
| Plugin MCP over stdio and streamable HTTP | both servers connected and both tools ran, named `mcp__<server>__<tool>` |
| Reserved environment variables | passed to the stdio server |
| Working directory | not honored: Claude Code's MCP configuration has no `cwd` field and the server ran in the project directory |
| Agent level `mcpServers` | loaded only after the project is trusted; untrusted projects silently drop them and a subagent with only MCP tools refuses to start |

#### Product probe: OpenCode, two major versions

The same script runs OpenCode headless (`opencode run --agent <entry>`, with `--standalone` on v2 and `--dir` on v1) against a local server that speaks the OpenAI chat completions protocol, configured as a custom provider. HOME and the XDG directories point into the temporary directory, so the user's configuration, skills, and data are untouched. v2.0.14 was probed first; v1.18.32 was then installed as a control because the v2 MCP result needed one.

| Checked | v1.18.32 | v2.0.14 |
|---|---|---|
| Entry instructions in the system prompt | yes | yes, with model and environment notes appended |
| Skills advertised before activation | `<available_skills>` block, body absent | same |
| Skill activation | `skill` tool takes `name`; body returned as the tool result and kept in later requests | `skill` tool takes `id`; same delivery |
| Subagents | tool named `task`, lists exactly the `permission.task` allowlist, child ran with own prompt, result returned | tool renamed `subagent`, same behavior |
| Plugin MCP servers | both connected | both connected within 300 ms |
| MCP tools offered to the model | `echostdio_echo_stdio` and `echohttp_echo_http` as function tools, plus generic MCP resource tools; both invoked | none, not as function tools and not through Code Mode: `execute` with `search({query: "echo"})` returned no items |
| Stdio working directory and reserved variables | `cwd` honored, `PLUGIN_ROOT` and `PLUGIN_DATA` present | not observable, no tool call reached the server |

So the v2 gap is a version change, not our configuration: the same files, the same servers, and the same scripted model work on v1. Between the two versions the agent directory stayed `.opencode/agent/` (singular; the documentation shows `agents/`, which neither version reads), the subagent tool was renamed from `task` to `subagent`, the `skill` tool's argument changed from `name` to `id`, and MCP tool exposure moved to Code Mode, where these servers did not appear. That is one product changing four things a compiler depends on across one major version, which is the case for probing per release.

Two more things the probe had to learn. OpenCode resolves its project from the `PWD` environment variable, not from the process working directory, so a subprocess launched with a different `cwd` runs against the wrong project. And with the user's real home directory, the skill catalog also lists every skill under `~/.claude/skills`, a live example of skills being additive rather than isolated.

Consequences for the grades: OpenCode's compile time `plugins` grade stays `resolved`, because the configuration is representable and v1 activates it fully. The v2 exposure gap is recorded in the probe evidence as a version specific observation whose cause was not determined from outside. Claude Code's `plugins` is `unsupported` for any stdio server, the same rule that already applied to CrewAI, LlamaIndex, AFM, and Copilot's cloud agent, and `resolved` for HTTP servers. The research fixture's plugin is HTTP only, so its grade did not change. Trust is host policy, but a compiler that emits agent level MCP servers should say that the project must be trusted first.

Strict outcome per field group, all agents:

| Field | LangGraph | CrewAI | LlamaIndex | Agno | OpenAI Agents | Google ADK | PydanticAI | Microsoft |
|---|---|---|---|---|---|---|---|---|
| core | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted |
| description | accepted | rejected | accepted | rejected | accepted | accepted | accepted | accepted |
| model | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| skills | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| plugins | rejected | accepted | rejected | accepted | accepted | accepted | accepted | accepted |
| subagents | accepted | rejected | rejected | rejected | accepted | rejected | accepted | accepted |

A rejected combined fixture says which field a target cannot preserve, not that the core is unportable. CrewAI is the one core rejection. Its role, goal, and backstory template fuses name, description, and instructions, and its template override drops role and goal only by collapsing the prompt into a single user message. That is a different agent abstraction, and the core should not be bent to pass it.

## Findings by field

### `name`

Six runtimes have a native name field. CrewAI has a role, which is prompt content, not identity. Google ADK requires Python identifiers, so `lead-researcher` becomes `lead_researcher` with an explicit map back. Five products have an identity field; OpenCode takes the identifier from the filename, which the compiler names after the logical name, so `resolved`.

The portable part is a stable logical identity for discovery, diagnostics, and packaging. Native spelling is not portable, and a native identifier may double as prompt content. Subagent references resolve to documents by path and to native tools by name, so the name must be stable, but it defines nothing else at runtime. A host may translate it only with a collision free mapping back, graded `resolved` rather than `preserved`.

### `description`

Google ADK, LlamaIndex, OpenAI Agents, PydanticAI, Microsoft, and all six products have native description or handoff metadata. LangGraph's compiled agent has none, so the adapter keeps descriptions in a catalog in the artifact metadata, never in the prompt, and children wrapped as tools carry theirs as the tool description. Agno injects the description into model context. CrewAI's nearest field is `goal`, which is behavioral.

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

Claude Code, Codex, Copilot, and OpenCode discover Agent Skills from a project directory the compiler fills (`.claude/skills`, `.agents/skills`, `.github/skills`, `.opencode/skills`) and load them on demand; the catalog is project wide rather than per agent, so `resolved`. Among frameworks, CrewAI, Agno, and Microsoft implement Agent Skills natively. Tests confirmed metadata only discovery, then invoked the native loader (`LoadSkillTool`, `get_skill_instructions`, `SkillsProvider.load_skill`). Each returns the full body on demand as a tool result, the dedicated tool activation the Agent Skills integration guide describes, so `preserved`. Microsoft gates loading behind approval by default; the adapter disables it and records that as host policy. LangGraph, LlamaIndex, OpenAI Agents, Google ADK, and PydanticAI have no skills concept; the adapter supplies the activation tool with the catalog in its description, so `resolved`. Claude Code, Codex, and AFM have static mappings with documented scope differences. Amplifier has none without a runtime module.

Not exercised, and therefore `unverified` everywhere: whether activated content survives context compaction, and whether bundled references, scripts, and assets are reachable on demand, since the fixture skills bundle none. Agent Skills does not define skill isolation, so `skills` is additive: the listed skills must be available to the agent, and ambient skills are host policy.

### `plugins`

Among products, Claude Code takes MCP servers per agent in the agent file, Codex per agent in its TOML, OpenCode once in `opencode.json` for every agent, and Copilot twice: per agent in the agent file for the cloud coding agent, and workspace wide in `.vscode/mcp.json` for VS Code. Copilot's cloud configuration has no working directory, so any stdio server is `unsupported` there; OpenCode's local server has `cwd`. Among frameworks, six construct native MCP clients from the plugin's `mcp.json` at build time. LangGraph and LlamaIndex cannot attach tools until a handshake succeeds; against the research fixture's unreachable endpoint they report `unsupported` rather than invent tools. Construction proves representability, not activation, so the research fixture keeps `plugins.activation` unverified and a separate probe supplies the live evidence.

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

### `subagents`

The generic `delegates` field promised one semantic and the hosts supplied six. The eight frameworks alone use: native agent as tool (OpenAI Agents, Microsoft, the latter in an isolated child session), no relationship primitive at all (LangGraph, PydanticAI), a child session that copies parent state and propagates changes back (Google ADK `AgentTool`), transfer of control through shared workflow state (LlamaIndex `can_handoff_to`), team collaboration under a leader (Agno `Team`), and delegation bound to tasks and process (CrewAI). Codex exposes a project catalog; AFM has nothing local. Lowering one of these into another invents orchestration policy, so the generic field is gone, and no `agents:` inventory replaces it: a profile describes one agent, a package may hold several, orchestration relates them.

What the mechanisms share is narrower and worth keeping. The products largely agree on it: Claude Code's `Agent(...)` allowlist, Copilot's `agents` list, and OpenCode's task permission all invoke a listed agent as a bounded task with its own instructions and return its summary to the caller, who keeps control. Codex does the same through a project wide catalog without a per agent allowlist. Draft 0.2 names that relation `subagents` and, like `skills` and `plugins`, makes it additive: the listed agents must be available; whether others are too, how deep calls nest, and what the child sees beyond the task text are host policy.

Graded against that contract, the picture splits by dimension:

- Products: Claude Code `preserved` for the main agent and `resolved` for nested subagents, where calls work but the allowlist is not enforced. Copilot `preserved` through its `agents` list. OpenCode `preserved` through `permission.task`. Codex `resolved`, because its project catalog makes the agents available without a per agent allowlist. Amplifier `preserved`. AFM `unsupported`.
- Frameworks: OpenAI Agents and Microsoft `preserved`. LangGraph and PydanticAI `resolved`, because an adapter tool implements the four properties on a framework without a relationship primitive. Google ADK `approximated`, because state flows both ways. LlamaIndex, Agno, and CrewAI `approximated`, because control transfers or the call is bound to a team or task graph.

The runtime traces in `generated/runtime/<target>/runtime.json` show the call and the return for every framework that reached `preserved` or `resolved`. The product grades rest on generated files and the products' documentation; product probes are the next pass.

## What changes in the profile

The draft in `spec/` applies these seven changes. Each traces to a finding above.

1. The core is `name` plus Markdown instructions. Nothing else is required.
2. `description`, `skills`, and `plugins` are optional, with one rule: if present, a strict host preserves the field's defined semantics or rejects the profile. Conformance is reported for the core and for each optional field.
3. `model.requires` stays in the document as an incubating, host resolved declaration until a capability vocabulary is standardized. `model.prefers`, model selection, and attestation move to the host binding.
4. `delegates` is replaced by the narrow, additive `subagents` relation: bounded task, own instructions, result returns, caller keeps control. No `agents:` inventory; packaging and orchestration are separate concerns.
5. The grading vocabulary gains `unverified` for properties that were not exercised. `omitted-preference` remains only for legacy reports.
6. Reports distinguish construction, activation, and execution evidence. Hosts implement Agent Plugins §7.2.1 and §9 themselves: the working directory default, placeholder expansion, and the reserved variables.
7. Host specific settings stay outside the document. No `x-<host>` sections, no extension map.

## Limits

- Deterministic model doubles avoided paid inference. They ran through each framework's real agent, tool, team or workflow, and runner code, but prove nothing about model behavior.
- The research fixture's `https://research.example.com/mcp` endpoint is unreachable by design. Live activation comes only from the probe, against a local echo server, not a shared reference server.
- Four product targets were lowered and verified, not executed. Claude Code and OpenCode (two major versions) were executed through probes; Codex is installed but its Homebrew cask is broken on this machine, and Copilot and Gemini CLI are not installed. Copilot cannot be pointed at a scripted endpoint and will stay static.
- The OpenCode v2 MCP finding is observational: the servers connected and the model was offered no MCP tool through either path v2 provides, while v1 exposes and runs them; the v2 cause was not determined.
- Skill grades follow the Agent Skills integration guide. Compaction and bundled resources were not exercised.
- The combined fixture's strict outcome is a construction result. The plugin probe fixture has no skills or subagents.
- The probe did not cover SSE, OAuth, colliding tool names, or activation failure reporting.
