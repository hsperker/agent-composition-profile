# Static lowering walkthrough

> Historical phase-one walkthrough. Runtime findings and the evidence-revised profile are in [`../EVIDENCE.md`](../EVIDENCE.md) and [`../spec/agent-composition-profile-v0.2-discussion-draft.md`](../spec/agent-composition-profile-v0.2-discussion-draft.md).

This walkthrough uses one portable source and one external deployment binding. The target files are generated artifacts.

## Portable source

`examples/research-team/lead.agent.md`:

```markdown
---
name: lead-researcher
description: >
  Investigates technical questions and produces evidence-backed conclusions.
  Use when a question needs research, independent criticism, and synthesis.
model:
  requires:
    reasoning: true
    tool-use: true
  prefers:
    vision-input: true
skills:
  - ./skills/source-evaluation
plugins:
  - ./plugins/web-research
delegates:
  - ./agents/explorer.agent.md
  - ./agents/critic.agent.md
---

# Instructions

Form a tentative conclusion from evidence.

Use `explorer` to gather primary sources. Use `critic` to challenge material assumptions and unsupported leaps.

Resolve the criticism and write the final answer yourself.
```

Notice what is absent: no provider, model name, credentials, native tool names, permission mode, sandbox, or target-specific section.

## External binding

The compiler invocation supplies non-portable deployment choices. A shortened excerpt:

```yaml
targets:
  amplifier:
    capabilities:
      reasoning: true
      tool-use: true
      vision-input: true
    model_roles:
      reasoning: reasoning

  claude-code:
    capabilities:
      reasoning: true
      tool-use: true
      vision-input: true
    model: opus
    entry_mode: main

  codex:
    capabilities:
      reasoning: true
      tool-use: true
      vision-input: true
    model: gpt-5.6-terra
    model_reasoning_effort: high

  afm:
    capabilities:
      reasoning: true
      tool-use: true
      vision-input: true
    model:
      name: deployment-model
      provider: deployment-provider
```

This file is not part of the Agent Composition Profile. A deployment may replace it without changing the agent.

## Amplifier lowering

A leaf agent becomes:

```markdown
---
meta:
  name: critic
  description: Challenges a tentative conclusion for unsupported assumptions and missed alternatives. Use after evidence has been gathered and a provisional answer exists.
  model_role: reasoning
agents: none
---

# Instructions

Try to falsify the tentative conclusion.

Identify unsupported claims, missing alternatives, and evidence that would change the answer.
```

The compiler also emits `bundle.md` and `behaviors/agents.yaml` to publish the roster.

This target preserves the direct delegate allowlist. The current proof of concept does not yet supply an Amplifier module that implements Agent Skills and Agent Plugins, so the full example fails strict compilation.

## Claude Code lowering

The entry agent becomes:

```markdown
---
name: lead-researcher
description: Investigates technical questions and produces evidence-backed conclusions. Use when a question needs research, independent criticism, and synthesis.
model: opus
mcpServers:
- research:
    type: http
    url: https://research.example.com/mcp
tools:
- Skill
- mcp__research__*
- Agent(explorer, critic)
---

# Instructions

Form a tentative conclusion from evidence.

Use `explorer` to gather primary sources. Use `critic` to challenge material assumptions and unsupported leaps.

Resolve the criticism and write the final answer yourself.
```

The compiler copies the Agent Skills into `.claude/skills/`. It avoids Claude's `skills` frontmatter field because that field eagerly injects complete skill content.

For a main agent, `Agent(explorer, critic)` preserves the declared direct allowlist. A nested agent with its own delegates fails strict compilation because Claude ignores the typed list inside subagent definitions.

## Codex lowering

The entry agent becomes:

```toml
name = "lead-researcher"
description = "Investigates technical questions and produces evidence-backed conclusions. Use when a question needs research, independent criticism, and synthesis."
model = "gpt-5.6-terra"
model_reasoning_effort = "high"
developer_instructions = """# Instructions

Form a tentative conclusion from evidence.

Use `explorer` to gather primary sources. Use `critic` to challenge material assumptions and unsupported leaps.

Resolve the criticism and write the final answer yourself.

## Portable delegate catalog

The source profile declares these delegates as available:

- explorer: Finds and assesses primary sources for a focused research question.
- critic: Challenges tentative conclusions for unsupported assumptions.
"""

[mcp_servers."research"]
url = "https://research.example.com/mcp"
required = true
```

The compiler copies skills into `.agents/skills/` and emits every reachable agent into `.codex/agents/`.

Codex uses project-wide agent and skill catalogs. The compiler therefore reports this as `resolved`, not `preserved`: the declared catalog is present, but it is not an exclusive per-parent allowlist.

## AFM lowering

A leaf researcher becomes:

```markdown
---
spec_version: 0.4.0
name: explorer
description: Finds and assesses primary sources for a focused research question. Use when claims need external evidence before synthesis.
model:
  name: deployment-model
  provider: deployment-provider
skills:
- type: local
  path: ./skills/source-evaluation
- type: local
  path: ./skills/query-planning
tools:
  mcp:
  - name: research
    transport:
      type: http
      url: https://research.example.com/mcp
---

# Role

Finds and assesses primary sources for a focused research question. Use when claims need external evidence before synthesis.

# Instructions

Search broadly, then prefer primary sources.

Return findings, source locations, and unresolved uncertainty. Do not write the final answer.
```

AFM preserves the leaf agent well. The full coordinator fails strict compilation because AFM 0.4.0 has no local delegate declaration.

## Why this is compilation, not only transpilation

A text-to-text transpiler usually rewrites syntax. This process must also:

- validate the package graph;
- resolve model requirements against deployment capabilities;
- expand Agent Plugins;
- copy Agent Skills into target discovery locations;
- generate target package structure;
- change catalog scope where the target requires it;
- reject unsupported semantics;
- emit a compatibility report.

“Transpiler” is understandable. “Compiler” or “lowering adapter” better describes the work.
