# Agent Composition Profile

**Discussion Draft 0.2 — evidence revision — 3 September 2026**

**Status:** Experimental input to the Agent Plugins Agent Profile incubation discussion. Not an adopted standard and not proposed as a competing standards effort.

> A Markdown document identifies an agent and supplies persistent instructions. Optional fields attach a discovery description, Agent Skills, and Agent Plugins; model requirements are incubating. The host selects models and owns orchestration.

```markdown
---
name: technical-researcher
description: Investigates technical questions using primary evidence.
model:
  requires:
    tool-use: true
skills:
  - ./skills/source-evaluation
plugins:
  - ./plugins/web-research
---

# Instructions

Investigate before concluding.

Cite the evidence behind the final answer.
```

This revision follows the runtime evidence in `EVIDENCE.md`. It reduces the required document to a name and instructions, keeps description, Agent Skills, and Agent Plugins as optional fields, marks host-resolved model requirements as incubating, moves model selection and preferences to the host, and removes local delegation.

## 1. Question and evidence

This draft asks for the smallest agent declaration whose meaning can survive unrelated runtimes. It composes Agent Skills and Agent Plugins rather than redefining them.

The accompanying experiment constructed native agents in LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, and Microsoft Agent Framework. It also retained the earlier static-lowering evidence for Amplifier, Claude Code, Codex, and WSO2 AFM.

The observed semantic intersection is narrower than draft 0.1:

- stable logical identity converges;
- persistent authoritative instructions converge;
- selection descriptions are common but not universal and are sometimes promoted into behavioral prompt content;
- Agent Skills and Agent Plugins are coherent optional dependencies; every runtime could activate skills through the published dedicated-tool pattern, but none exercised session durability;
- model requirements can be declared portably but are only ever resolved by a host attestation; no SDK verified them natively;
- delegation, handoff, graph transition, and team collaboration are observably different mechanisms.

## 2. Goals

A conforming loader or adapter:

1. preserves the document's logical identity and persistent instruction authority;
2. preserves the defined semantics of every optional field present or rejects strict execution;
3. reports every source-to-target mapping explicitly;
4. keeps concrete models, permissions, credentials, and orchestration outside the portable source;
5. never claims conformance after silently dropping a declaration.

The profile targets portable intent, not identical generated output, provider message shape, or scheduler behavior.

## 3. Scope

The profile defines:

```text
agent document
├── required
│   ├── logical name (metadata)
│   └── persistent Markdown instructions (behavioral core)
├── optional
│   ├── selection description
│   ├── Agent Skill references
│   └── Agent Plugin references
└── incubating
    └── model requirements
```

The host or deployment defines:

```text
runtime binding
├── concrete model, provider, endpoint, capability attestation, and selection preferences
├── credentials and authorization
├── native tools and ambient capabilities
├── agent relationships and orchestration
├── state, memory, context, and history
├── sandbox, approvals, budgets, retries, and timeouts
└── interfaces, services, and deployment
```

This profile is not a workflow language, deployment manifest, model registry, permission system, or remote-agent protocol.

## 4. Document format

An agent document is UTF-8 Markdown with one YAML frontmatter mapping followed by a non-empty Markdown body.

The frontmatter fields are:

| Field | Required | Meaning |
|---|---:|---|
| `name` | Yes | Stable package-level logical identity. |
| `description` | No | Metadata used to understand, display, discover, or select the agent. |
| `model` | No, incubating | `requires` only: model capabilities the agent needs, resolved by the host. |
| `skills` | No | Agent Skills that must be available to this agent. |
| `plugins` | No | Agent Plugins required by this agent. |

No other top-level field is defined in draft 0.2. Empty optional arrays, empty descriptions, and empty requirement maps are invalid.

### 4.3 Required and optional fields

`name` and the Markdown body are required. Every other field is optional, with one rule: if an optional field is present, a strict host MUST preserve its defined semantics or reject the profile. It MUST NOT ignore the field. A host that does not implement, say, Agent Plugins is still a conforming host for documents that do not use `plugins`.

There is no negotiation protocol. Conformance is reported for the required core and for each optional field present (section 12).

The companion JSON Schema validates the decoded frontmatter. This text additionally governs safe YAML parsing, Markdown, path containment, and referenced packages.

### 4.1 Safe YAML

Loaders MUST:

- parse with YAML 1.2 Core Schema behavior;
- reject duplicate keys, custom tags, anchors, aliases, and merge keys;
- accept only JSON-representable values;
- reject unknown top-level fields;
- perform no environment expansion, template substitution, command execution, or network access while parsing.

Comments carry no semantics.

### 4.2 Markdown body

The body after frontmatter is the agent's persistent instructions. It MUST contain non-whitespace text.

Loaders MUST treat the body as literal Markdown. A target may translate it into a native instruction representation, but preservation requires that it remain authoritative behavioral context on every invocation. Ordinary task input, tool output, delegate output, and description text MUST NOT be silently promoted to equivalent instruction authority.

The profile does not require a particular provider role such as `system` or `developer`.

## 5. `name`

`name` MUST contain 1–64 ASCII characters and match:

```regex
^[a-z0-9]+(?:-[a-z0-9]+)*$
```

The value is the logical package identity. It is required metadata for discovery, diagnostics, and packaging; it does not by itself define runtime behavior. Draft 0.2 has no intra-document references, so no field depends on it.

A target whose native grammar is narrower MAY use a deterministic native alias when it:

- records the source-to-native mapping;
- detects collisions before execution;
- resolves all internal references through the same mapping;
- exposes the logical source name in diagnostics.

Such a mapping is `resolved`, not byte-for-byte `preserved`. Google ADK, for example, requires Python identifiers and cannot accept a legal source name containing a hyphen.

## 6. `description`

`description` is human- or model-readable metadata used to understand, display, discover, or select an agent. It MUST NOT be merged into the agent's behavioral instructions without explicit semantics.

A target preserves it when the value remains metadata used for discovery, routing, or tool selection. A target that can only put it into behavioral prompt content MUST report `approximated`. A same-named native field is not automatically preservation, and the absence of one is not automatically `unsupported`: a host may retain the description in its own catalog, registry, UI, or diagnostics and report `resolved`, provided the report names that surface. Only a host with no place for the metadata at all reports `unsupported`.

A catalog or distribution profile MAY require `description`; for a directly invoked agent it is optional.

Omission carries no negative capability claim. A host may generate display metadata, but generated text is not part of the portable identity.

## 7. Agent Skills

Each `skills` entry is a relative path to an Agent Skill directory containing `SKILL.md`.

A `skills` entry is additive: the listed skills MUST be available to this agent. The profile does not claim they are the only skills the agent may see. Agent Skills does not define skill isolation; exclusivity is host authorization policy and stays outside the document.

Preservation requires the activation semantics of the Agent Skills specification and its integration guide:

1. only name and description are disclosed initially;
2. activation happens on demand, by the model or the user;
3. the complete skill instructions enter model context on activation;
4. referenced resources and scripts are reachable on demand and never eagerly loaded;
5. host authorization remains the upper bound.

The delivery mechanism is secondary. The integration guide names file-read activation and dedicated-tool activation as conforming patterns, and in both the model receives the instructions as a tool result. A native implementation is `preserved`; an adapter that supplies the dedicated activation tool for a framework without a skills concept is `resolved`. Injecting full skill bodies eagerly, or truncating them, is `approximated`.

Session durability and resource access are separate properties. The guide asks hosts to protect activated skill content from context compaction and to make bundled references, scripts, and assets reachable on demand. A report that did not exercise compaction MUST record `skills.durability` as `unverified`; one whose fixture bundles no resources MUST record `skills.resources` as `unverified`. Neither is preserved and neither is approximated.

The profile does not duplicate the Agent Skills file format.

## 8. Agent Plugins

Each `plugins` entry is a relative path to an Agent Plugin package.

A plugin reference requires every valid standard component in that package. A runtime may expand the package into native Agent Skills and MCP clients; it need not retain a native plugin wrapper.

Preservation requires:

- the plugin's effective Agent Skills to obey section 7;
- every declared MCP server to remain attached at the same agent scope;
- transport, endpoint, headers, environment, working directory, and other standard settings to be retained where declared;
- activation or authorization failure to block that invocation rather than silently remove the component.

Agent Plugins and MCP retain ownership of their component formats and protocol semantics. This profile adds only the agent-to-plugin composition edge.

This strictness is a composition-level rule of the Agent Profile, not a change to Agent Plugins conformance. Agent Plugins permits a client to support only some component types and to ignore the rest. When a profile author declares a plugin as part of this agent, a strict profile host must preserve every component that plugin instance requires or reject this profile; a client that ignores components remains a conforming Agent Plugins client, but not a strict host for this profile.

## 9. Paths and packages

Skill and plugin paths resolve relative to the declaring document.

Every path MUST:

- begin with `./` or `../`;
- be relative and contain no NUL, control character, backslash, URI scheme, or platform drive prefix;
- exist and have the required file type;
- remain within the canonical package root after lexical and filesystem resolution, including symlinks and equivalent mechanisms.

Two entries in one field resolving to the same canonical target are duplicates and MUST be rejected.

Effective skill names across direct skills and plugin-supplied skills MUST be unique for one agent.

## 10. Model requirements are declared here and resolved by the host

`model.requires` is an optional, incubating field: a map of capability names to `true`, stating what the agent needs in order to work. The agent author knows this; the deployment knows which concrete model provides it.

The evidence supports portable model requirements as a concept. It does not yet provide a portable capability vocabulary, and a requirement is only interoperable when its name has a standardized meaning. The field therefore stays out of the first normative proposal and is carried here as incubating.

| Concern | Owner |
|---|---|
| Declare required model properties | Agent document |
| Define the capability vocabulary | External governed registry or a future profile revision |
| Select a concrete model | Host or deployment |
| Attest that the model satisfies the requirements | Host or deployment |
| Choose among otherwise valid models | Host or deployment |

The experiments resolved every requirement through a host attestation such as `tool-use: true`; no SDK exposed a shared, trustworthy capability contract. That shows requirements are host-resolved, not that they are host-authored. A report MUST classify a requirement `resolved` only when the binding attests it and `unsupported` otherwise, and MUST NOT imply that the runtime verified it.

Objectively checkable capabilities such as `tool-use`, `vision-input`, or `structured-output` are the intended vocabulary. `reasoning` has no shared operational definition across SDKs and is at risk of removal or reclassification as a locally attested profile.

Draft 0.2 has no `model.prefers`. A preference that does not affect whether the agent can execute is deployment selection policy and lives in the host binding.

## 11. Agent relationships belong to orchestration

Draft 0.2 has no `delegates` field.

The tested mechanisms did not converge:

- bounded agent-as-tool calls;
- handoff or active-agent transfer;
- workflow or graph transitions;
- shared-state nested runs;
- team/member collaboration;
- application-authored function tools;
- catalogs with no per-parent invocation contract;
- no local equivalent.

These mechanisms differ in control ownership, state sharing, task schemas, result handling, and conversation continuity. A single generic `delegates` field wrongly suggests they share one semantic; that overload is the reason for removal. An adapter MUST NOT lower one mechanism into another while claiming semantic preservation.

Adapter-authored implementations are not illegitimate in themselves. Where a source contract is explicit, for example a fresh child run with task in, text out, and control returning to the parent, an adapter tool that implements it is `resolved`. A future optional field may define one explicitly typed relationship such as `agent-as-tool`; draft 0.2 does not attempt to cover multi-agent orchestration.

Draft 0.2 defines no agent inventory either. An Agent Profile describes one agent; a package may contain several agents; orchestration defines relationships among them. The latter two are left to packaging and orchestration when a use case emerges.

Remote agents remain the domain of protocols such as A2A.

## 12. Compatibility reporting

For every declared source semantic and every agent, an adapter emits exactly one classification:

| Status | Meaning |
|---|---|
| `preserved` | The target has materially the same native semantic. |
| `resolved` | An explicit mechanical binding or reversible mapping preserves meaning. |
| `approximated` | The target can run something similar, but observable meaning changes. |
| `unsupported` | No working mapping was demonstrated. |
| `unverified` | The mapping exists but a property was not exercised. It asserts no mismatch and never stands in for `approximated`. |
| `omitted-preference` | Legacy draft 0.1 reports only: a non-binding model preference was not selected. |

Strict mode MUST reject any required source semantic classified `approximated` or `unsupported`. `unverified` findings do not block strict mode but MUST be listed in the report. Diagnostic mode MAY construct the representable subset only when the report marks every loss. No mode may silently discard source semantics.

Reports MUST also state an outcome for the required core and for each optional field present: description, model, skills, plugins, and, for draft 0.1 documents, delegates. The reference reports carry these under a `modules` key. A combined fixture that is rejected does not show that the core is non-portable; it shows which optional field the target cannot preserve.

Reports SHOULD distinguish:

1. native object construction;
2. capability activation;
3. runtime execution.

One does not prove the next.

## 13. Host policy and ambient capabilities

Declarations request capabilities; they never grant permission. Host policy remains the upper bound for secrets, network, files, process execution, approvals, models, and budgets.

A runtime SHOULD report ambient skills, plugins, tools, and agents that can materially affect behavior. Strict testing SHOULD remove optional ambient capabilities where the host can do so safely.

Target-specific settings remain in external bindings. Draft 0.2 defines no `x-<host>` sections or extension map.

## 14. Evidence status

The shared research fixture produced machine-readable reports for twelve targets. Eight targets used real SDK objects and native runners; four retained static-lowering evidence. Seven of eight runtime targets accepted the required core; CrewAI's role, goal, and backstory prompt template approximates both name and instructions. OpenAI Agents SDK, PydanticAI, and Microsoft Agent Framework accepted the combined draft 0.1 fixture with skill durability and resource access unverified; the other four each failed one or two optional fields, most often description or delegates.

The decisive findings were:

- native-looking fields can have different authority (`description`, CrewAI `goal`, and `backstory`);
- Agent Skills activation converged on the published dedicated-tool pattern in all eight runtimes, while session durability was exercised by none;
- MCP object construction does not prove endpoint activation;
- one generic `delegates` field cannot name the mechanism a target actually uses;
- dependency isolation is part of a reproducible multi-framework experiment.

The classifications are recorded reviewer judgments about each native mechanism, backed by construction tests and deterministic runtime smoke tests. They are not measurements derived from the traces. See `EVIDENCE.md`, individual reports under `generated/runtime/`, and the generated `generated/runtime/matrix.json`.

## 15. Adoption path

This draft should be discussed as implementation evidence for the existing Agent Plugins Agent Profile incubation effort.

Before adoption, the community should require:

1. independent implementations of the narrowed document;
2. live Agent Plugin/MCP activation against a shared test server;
3. conformance fixtures for instruction authority, skill disclosure, and skill durability under compaction;
4. negative tests for every required failure;
5. a stable owner, versioning policy, and compatibility process.

The experiment does not justify a separate standards brand.

## References

- Agent Skills specification: https://agentskills.io/specification
- Agent Plugins specification: https://agent-plugins.org/specification
- Model Context Protocol specification: https://modelcontextprotocol.io/specification/
- A2A Protocol specification: https://a2a-protocol.org/latest/specification/
