# Reference compiler implementation report

> Historical phase-one static evidence. The eight-framework runtime experiment supersedes its profile conclusions; see [`../EVIDENCE.md`](../EVIDENCE.md). These artifacts remain in the matrix as `static-lowering` evidence.

**Date:** 3 September 2026

**Source:** Agent Composition Profile discussion draft 0.1

## Conclusion

The profile is concrete enough to compile. It is not yet portable enough to call standardized.

The proof of concept establishes three things:

1. Identity, selection description, Markdown instructions, and capability-based model selection lower cleanly across several targets.
2. Agent Skills and Agent Plugins can often be expanded into native skill and MCP mechanisms, but target catalog scope and transport details matter.
3. Local delegate composition is the least converged core feature. Amplifier preserves it directly. Claude Code preserves it for a main agent but not as a typed allowlist inside nested subagents. Codex exposes all custom agents through a project catalog. AFM 0.4.0 has no local delegate field.

The implementation also disproves the need for host extensions inside the portable source. Every target needs deployment input, but none needs that input to change the agent declaration.

## Architecture

```text
.agent.md files
Agent Skills
Agent Plugins
      │
      ▼
package parser and semantic validator
      │
      ├── target-neutral model
      │
      ├── package graph
      │
      └── compatibility findings
             ▲
             │
external target binding
             │
      ┌──────┼────────┬──────────┐
      ▼      ▼        ▼          ▼
 Amplifier  Claude   Codex       AFM
 bundle     project  project     .afm.md
```

The target binding is intentionally outside the portable package. It attests model capabilities and supplies deployment values such as an Amplifier model role, a Claude model alias, a Codex model and effort, or an AFM provider binding.

## Compatibility vocabulary

Each adapter records one status per semantic feature:

| Status | Meaning |
|---|---|
| `preserved` | The target has equivalent native semantics. |
| `resolved` | A binding, package expansion, or documented target mechanism preserves the requirement, but not through a one-to-one field. |
| `approximated` | The target provides similar behavior, not equivalent behavior. |
| `unsupported` | A required semantic cannot be represented. Strict compilation fails. |
| `omitted-preference` | An optional model preference cannot be met. |

The compiler never labels an unsupported mapping as preserved merely because it can write syntactically valid output.

## Implemented targets

### Amplifier Foundation

Generated structure:

```text
bundle.md
behaviors/agents.yaml
agents/<name>.md
compatibility-report.json
```

Mappings:

| Profile semantic | Amplifier result |
|---|---|
| `name` | `meta.name` — preserved |
| `description` | `meta.description` — preserved |
| Markdown body | Agent Markdown body/system prompt — preserved |
| `model.requires.reasoning` | External binding selects `meta.model_role: reasoning` — resolved |
| `delegates` | Top-level `agents` allowlist — preserved |
| Agent Skills | No demonstrated direct reference with Agent Skills progressive-disclosure semantics — unsupported without a module shim |
| Agent Plugins | No direct package lowering in the agent file — unsupported without a module/bundle adapter |

A leaf agent compiles strictly. The full example emits a diagnostic bundle and rejects strict compilation because the skill and plugin semantics are not yet implemented in Amplifier.

### Claude Code

Generated structure:

```text
.claude/agents/<name>.md
.claude/skills/<skill>/SKILL.md
compatibility-report.json
```

Mappings:

| Profile semantic | Claude Code result |
|---|---|
| Identity and body | Native subagent frontmatter and Markdown — preserved |
| Model requirements | External binding selects a model alias — resolved |
| Agent Skills | Copied to project skill discovery and exposed through the `Skill` tool — resolved |
| Agent Plugin MCP | Lowered to agent-scoped `mcpServers` and `mcp__<server>__*` tools — resolved |
| Entry-agent delegates | `Agent(explorer, critic)` when launched as the main agent — preserved |
| Nested typed delegate catalog | Claude ignores the type list in a subagent definition — unsupported |

The compiler deliberately does **not** use Claude's `skills` frontmatter field. That field eagerly injects full skill content at startup. Project skill discovery plus the `Skill` tool is closer to Agent Skills progressive disclosure.

The example graph compiles strictly because only the main entry agent delegates. A fixture in which `explorer` delegates to `critic` fails strict compilation.

### OpenAI Codex

Generated structure:

```text
.codex/config.toml
.codex/agents/<name>.toml
.agents/skills/<skill>/SKILL.md
compatibility-report.json
```

Mappings:

| Profile semantic | Codex result |
|---|---|
| Identity | `name` and `description` — preserved |
| Markdown body | `developer_instructions` — preserved |
| Model requirements | External binding selects `model` and `model_reasoning_effort` — resolved |
| Agent Skills | Copied to repository `.agents/skills` discovery — resolved |
| Agent Plugin MCP | Supported `stdio` and streamable HTTP servers become per-agent `mcp_servers` — resolved |
| Delegates | Every reachable agent becomes a project custom agent; the direct catalog is repeated in instructions — resolved, not structurally preserved |

Codex discovers custom agents and skills through project-wide catalogs. The compiler therefore reports the following scope change instead of hiding it:

- skills become ambient to the project rather than private to one agent;
- all reachable custom agents are discoverable globally;
- the direct delegate catalog is not an exclusive per-parent allowlist.

Agent Plugins `sse` transport is rejected for Codex because the current native configuration does not provide an equivalent. Diagnostic mode omits that server and reports the loss.

### WSO2 Agent-Flavored Markdown 0.4.0

Generated structure:

```text
<name>.afm.md
skills/<skill>/SKILL.md
compatibility-report.json
```

Mappings:

| Profile semantic | AFM result |
|---|---|
| Name and description | Native frontmatter — preserved |
| Markdown body | Rendered under required `# Role` and `# Instructions` headings — preserved |
| Model requirements | External binding supplies AFM's concrete model fields — resolved |
| Agent Skills | Copied and referenced as local skills — preserved |
| Agent Plugin MCP | Representable `stdio` or streamable HTTP subset becomes `tools.mcp` — resolved |
| Local delegates | No AFM 0.4.0 field — unsupported |

AFM cannot represent every valid Agent Plugins 1.0.0 MCP setting. The compiler reports and rejects, in strict mode, at least:

- Agent Plugins `sse` transport;
- arbitrary HTTP headers;
- `cwd` for a stdio server.

## Results for the example package

| Build | Strict | Compatibility summary |
|---|---:|---|
| `amplifier-critic-strict` | Pass | Leaf identity, instructions, model role, and no-delegation contract preserved/resolved |
| `amplifier-full-diagnostic` | Fail | Four unsupported skill/plugin mappings across the team |
| `claude-code-full-strict` | Pass | Full example graph preserved or resolved |
| `codex-full-strict` | Pass | Full example graph resolved with global-catalog scope reported |
| `afm-explorer-strict` | Pass | Leaf skills and MCP preserved/resolved |
| `afm-full-diagnostic` | Fail | Entry agent's local delegates unsupported |

The machine-readable reports under `generated/*/compatibility-report.json` are the authoritative result of each build.

## Changes forced by implementation

The implementation changed the draft in ways that a format-only exercise would likely have missed.

### Host extensions were removed

They were unnecessary for compilation and harmful to the abstraction boundary. Target settings now enter through an external binding.

### Reachable agent names became package-wide unique

Amplifier can scope agents through bundles, but Claude Code and Codex expose project-level named catalogs. Allowing two reachable declarations with the same name makes generated filenames and delegation ambiguous.

### Skill-name scope became explicit

The source can define per-agent catalogs. Claude Code and Codex discover project skills globally. The compiler detects different skill directories with the same name and rejects a strict build rather than copying one arbitrarily.

### Agent Plugin transport fidelity became testable

A valid Agent Plugin is not automatically representable in every harness. The compiler validates the pinned Agent Plugins 1.0.0 schemas, then evaluates each target's actual transport and field surface.

### “Compiler” is more accurate than “transpiler”

The process does more than rewrite syntax. It resolves requirements, expands packages, changes directory layout, binds deployment values, checks graph constraints, and rejects semantic loss.

## Validation performed

The automated suite covers:

- YAML 1.2-style booleans without modifying PyYAML's global loader;
- duplicate YAML keys, anchors, aliases, tags, and unknown fields;
- frontmatter/body parsing;
- canonical package containment;
- Agent Skill name and directory validation;
- pinned Agent Plugins 1.0.0 `plugin.json` and `mcp.json` schemas;
- duplicate effective skill names;
- package-wide agent-name uniqueness;
- direct and indirect delegate cycles;
- model requirement resolution;
- strict versus diagnostic compilation;
- YAML and TOML parsing of generated files;
- target-specific delegate, skill, plugin, and transport losses.

Run `./scripts/verify.sh` to reproduce the current evidence.

## What this does not prove

The target CLIs were unavailable in the build environment, and the environment could not install them from the network. The experiment therefore does not prove that a real target runtime will start every emitted package or produce equivalent model behavior.

Before any 1.0 claim, the project needs integration tests that:

1. load the generated artifacts in pinned target versions;
2. invoke the same behavioral fixture;
3. verify model selection, skill discovery, MCP activation, and delegation traces;
4. compare compatibility reports with observed runtime behavior;
5. run in at least two unrelated harnesses maintained by different organizations.

The current result is stronger than a paper mapping and weaker than demonstrated runtime interoperability.
