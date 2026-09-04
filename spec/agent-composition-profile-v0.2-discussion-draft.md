# Agent Composition Profile

**Discussion Draft 0.2 — evidence revision — 3 September 2026**

**Status:** Experimental input to the Agent Plugins Agent Profile incubation discussion. Not an adopted standard and not proposed as a competing standards effort.

> A Markdown document identifies an agent, supplies persistent instructions, and may attach a discovery description, Agent Skills, and Agent Plugins. The host supplies models and orchestration.

```markdown
---
name: technical-researcher
description: Investigates technical questions using primary evidence.
skills:
  - ./skills/source-evaluation
plugins:
  - ./plugins/web-research
---

# Instructions

Investigate before concluding.

Cite the evidence behind the final answer.
```

This revision follows the runtime evidence in `EVIDENCE.md`. In particular, it removes model policy and local delegation from the portable document.

## 1. Question and evidence

This draft asks for the smallest agent declaration whose meaning can survive unrelated runtimes. It composes Agent Skills and Agent Plugins rather than redefining them.

The accompanying experiment constructed native agents in LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, and Microsoft Agent Framework. It also retained the earlier static-lowering evidence for Amplifier, Claude Code, Codex, and WSO2 AFM.

The observed semantic intersection is narrower than draft 0.1:

- stable logical identity converges;
- persistent authoritative instructions converge;
- selection descriptions are common but not universal and are sometimes promoted into behavioral prompt content;
- Agent Skills and Agent Plugins are coherent optional dependencies, but not every runtime can preserve their scope or authority;
- model capabilities are external deployment attestations, not common agent-runtime fields;
- delegation, handoff, graph transition, and team collaboration are observably different mechanisms.

## 2. Goals

A conforming loader or adapter:

1. preserves the document's logical identity and persistent instruction authority;
2. preserves every declared optional semantic or rejects strict execution;
3. reports every source-to-target mapping explicitly;
4. keeps concrete models, permissions, credentials, and orchestration outside the portable source;
5. never claims conformance after silently dropping a declaration.

The profile targets portable intent, not identical generated output, provider message shape, or scheduler behavior.

## 3. Scope

The profile defines:

```text
agent document
├── logical name
├── optional selection description
├── persistent Markdown instructions
├── optional Agent Skill references
└── optional Agent Plugin references
```

The host or deployment defines:

```text
runtime binding
├── model, provider, endpoint, and model capability policy
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
| `description` | No | Human-readable selection or discovery hint. |
| `skills` | No | Agent Skills available to this agent. |
| `plugins` | No | Agent Plugins required by this agent. |

No other top-level field is defined in draft 0.2. Empty optional arrays and empty descriptions are invalid.

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

The value is the logical package identity. A target whose native grammar is narrower MAY use a deterministic native alias when it:

- records the source-to-native mapping;
- detects collisions before execution;
- resolves all internal references through the same mapping;
- exposes the logical source name in diagnostics.

Such a mapping is `resolved`, not byte-for-byte `preserved`. Google ADK, for example, requires Python identifiers and cannot accept a legal source name containing a hyphen.

## 6. `description`

`description` is optional selection or discovery metadata describing what the agent does and when it is suitable.

A target preserves it when the value remains metadata used for discovery, routing, or tool selection. A target that can only put it into behavioral prompt content MUST report `approximated`. A target with no discovery-description representation reports `unsupported`.

Omission carries no negative capability claim. A host may generate display metadata, but generated text is not part of the portable identity.

## 7. Agent Skills

Each `skills` entry is a relative path to an Agent Skill directory containing `SKILL.md`.

The effective skill catalog is agent-private. Preservation requires the semantics of Agent Skills, including:

1. metadata-first discovery by name and description;
2. full instruction disclosure only when activated;
3. activated skill content entering context with instruction authority;
4. contained and explicit access to referenced resources and scripts;
5. host authorization remaining the upper bound.

Reading full skill text into process memory is not itself a disclosure failure. The relevant boundary is what enters model context.

A function tool that merely returns `SKILL.md` as ordinary tool output is `approximated`, because tool output does not have persistent instruction authority. Strict execution MUST reject that mapping.

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

## 9. Paths and packages

Skill and plugin paths resolve relative to the declaring document.

Every path MUST:

- begin with `./` or `../`;
- be relative and contain no NUL, control character, backslash, URI scheme, or platform drive prefix;
- exist and have the required file type;
- remain within the canonical package root after lexical and filesystem resolution, including symlinks and equivalent mechanisms.

Two entries in one field resolving to the same canonical target are duplicates and MUST be rejected.

Effective skill names across direct skills and plugin-supplied skills MUST be unique for one agent.

## 10. Models belong to the host

Draft 0.2 has no `model` field.

The experiments could only satisfy `reasoning`, `tool-use`, and `vision-input` through external binding assertions. The eight SDKs expose no shared, trustworthy capability vocabulary with equivalent operational meaning.

A host binding MAY declare and attest model preconditions or preferences. Those declarations are deployment evidence and MUST remain outside this document. A future portable model requirement would require a governed capability vocabulary and interoperable conformance tests before entering the profile.

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

These mechanisms differ in control ownership, state sharing, task schemas, result handling, and conversation continuity. An adapter MUST NOT lower one into another while claiming semantic preservation.

A package or installer MAY maintain a non-behavioral inventory of agent documents. Such an `agents:` manifest is a composition convention, not a promise that any agent can invoke another. Typed relationship mechanisms may be proposed separately when their semantics and evidence are explicit.

Remote agents remain the domain of protocols such as A2A.

## 12. Compatibility reporting

For every declared source semantic and every agent, an adapter emits exactly one classification:

| Status | Meaning |
|---|---|
| `preserved` | The target has materially the same native semantic. |
| `resolved` | An explicit mechanical binding or reversible mapping preserves meaning. |
| `approximated` | The target can run something similar, but observable meaning changes. |
| `unsupported` | No working mapping was demonstrated. |
| `omitted-preference` | Legacy draft 0.1 reports only: a non-binding model preference was not selected. |

Strict mode MUST reject any required source semantic classified `approximated` or `unsupported`. Diagnostic mode MAY construct the representable subset only when the report marks every loss. No mode may silently discard source semantics.

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

The shared research fixture produced machine-readable reports for twelve targets. Eight targets used real SDK objects and native runners; four retained static-lowering evidence. Only Microsoft Agent Framework accepted every draft 0.1 field under strict runtime classification. That does not validate draft 0.1 as portable; the cross-framework failures caused this revision.

The decisive findings were:

- native-looking fields can have different authority (`description`, CrewAI `goal`, and `backstory`);
- progressive skill disclosure is not preserved by returning instructions as ordinary tool output;
- MCP object construction does not prove endpoint activation;
- a runnable delegation adapter may still invent control-flow semantics;
- dependency isolation is part of a reproducible multi-framework experiment.

See `EVIDENCE.md`, individual reports under `generated/runtime/`, and the generated `generated/runtime/matrix.json`.

## 15. Adoption path

This draft should be discussed as implementation evidence for the existing Agent Plugins Agent Profile incubation effort.

Before adoption, the community should require:

1. independent implementations of the narrowed document;
2. live Agent Plugin/MCP activation against a shared test server;
3. conformance fixtures for instruction authority and skill disclosure;
4. negative tests for every required failure;
5. a stable owner, versioning policy, and compatibility process.

The experiment does not justify a separate standards brand.

## References

- Agent Skills specification: https://agentskills.io/specification
- Agent Plugins specification: https://agent-plugins.org/specification
- Model Context Protocol specification: https://modelcontextprotocol.io/specification/
- A2A Protocol specification: https://a2a-protocol.org/latest/specification/
