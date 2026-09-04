# Agent Composition Profile — Runtime Interoperability Proof

Continue the Agent Composition Profile interoperability project from the supplied artifacts.

## Goal

Test whether the proposed Agent Composition Profile captures a genuine cross-framework semantic abstraction rather than merely common configuration syntax.

Do not optimize for proving the proposal correct. **Try to falsify it.**

If implementation evidence shows that a proposed semantic does not genuinely converge across frameworks, change the proposal or recommend removing that semantic.

## Existing work

The handoff contains:

- the current discussion draft;
- its companion schema;
- a lowering walkthrough;
- an implementation report;
- the existing reference compiler and fixtures.

The current proof of concept has static lowering targets for:

- Amplifier Foundation;
- Claude Code;
- OpenAI Codex;
- WSO2 Agent-Flavored Markdown.

Treat those mappings as prior evidence, not as assumptions that the source profile is correct.

## Implement executable runtime targets

Add real, tested runtime adapters for these common and architecturally distinct frameworks:

1. LangChain / LangGraph
2. CrewAI
3. LlamaIndex
4. Agno
5. OpenAI Agents SDK
6. Google Agent Development Kit (ADK)
7. PydanticAI
8. Microsoft Agent Framework

Use current stable releases and pin every tested dependency.

Do not add AutoGen or Semantic Kernel as primary targets. They may be useful only as historical/contextual comparisons.

## What “implemented” means

Do not merely emit illustrative Python files.

For each framework:

1. construct real native framework agent objects from the portable profile;
2. use actual framework APIs;
3. execute those objects through the framework runtime where practical;
4. test the resulting behavior;
5. emit a machine-readable compatibility report.

Separate model-independent integration tests from tests requiring paid or remote inference.

Where a framework provides an official deterministic test/fake model, use it for framework-behavior tests. Do not mock away the framework semantics under test.

## Treat every proposed field as a hypothesis

Do not assume that the current Agent Composition Profile is correct.

For every proposed semantic answer two separate questions:

1. **Can this be made to run in the target framework?**
2. **Does the native mapping preserve the source semantics?**

Do not confuse successful execution with semantic interoperability.

The current hypotheses are:

- `name`
- `description`
- Markdown instructions
- `model.requires`
- `model.prefers`
- `skills`
- `plugins`
- `delegates`

For each semantic, inspect the native mechanisms across all implemented targets and classify the cross-framework abstraction as one of:

- **portable core** — strong semantic convergence;
- **optional capability** — meaningful portable semantics, but not universally implementable;
- **composition convention** — useful package structure without guaranteed runtime semantics;
- **host/runtime concern** — meaning depends materially on the target harness;
- **remove** — the proposed abstraction does not survive implementation evidence.

Do not use a simple majority threshold such as “6 of 8 frameworks support it.” Look for a coherent semantic intersection.

## Source semantics under test

Attempt to preserve:

- `name`;
- `description`;
- Markdown instructions;
- model capability requirements;
- Agent Skills;
- Agent Plugins / MCP capabilities;
- local agent relationships currently represented as `delegates`.

Concrete model/provider configuration must remain outside the portable profile and enter through target bindings or deployment configuration.

Do not add target-specific sections to the portable agent declaration.

## Compatibility classification

For every source semantic in every target, classify the mapping as exactly one of:

- `preserved`
- `resolved`
- `approximated`
- `unsupported`
- `omitted-preference`

Definitions:

`preserved`
: The target has semantically equivalent native behavior.

`resolved`
: External binding or mechanical expansion preserves the source requirement without changing its meaning.

`approximated`
: The target offers similar behavior but changes source semantics.

`unsupported`
: The semantic cannot be represented.

`omitted-preference`
: An optional preference cannot be satisfied.

Strict mode MUST reject required semantics classified as `approximated` or `unsupported`.

Never silently discard source semantics.

## Common behavioral fixture

Use the existing `research-team` package unchanged as the main source fixture:

- `lead-researcher`
- `explorer`
- `critic`
- `source-evaluation` Agent Skill
- `web-research` Agent Plugin / MCP capability

The portable source must remain identical across all targets.

If an additional fixture is necessary to expose a semantic distinction, add the smallest possible fixture and explain why the original fixture was insufficient.

## Required tests

For each target, establish whether:

1. the native object contains the expected agent identity;
2. Markdown instructions reach a persistent agent-level instruction mechanism;
3. model requirements resolve through an external target binding;
4. Agent Skills remain discoverable with semantics consistent with progressive disclosure;
5. plugin-provided MCP capabilities become available to the intended agent;
6. the lead agent can invoke or otherwise relate to an allowed specialist according to the target’s native multi-agent mechanism;
7. the specialist executes with its own instructions and capability set where the native mechanism claims isolation;
8. a result or control outcome returns according to the native mechanism;
9. unavailable required capabilities fail explicitly;
10. compatibility reports match observed runtime behavior.

Add negative fixtures wherever a target could silently broaden, weaken, or change the portable declaration.

## Delegation is a hypothesis, not an assumption

Challenge `delegates` especially hard.

The present proposal roughly assumes:

```text
delegate(agent-name, task-text) -> result-text | error
```

For every target determine what the native mechanism actually is. Distinguish at least:

- bounded task delegation;
- agent-as-tool;
- handoff / transfer of control;
- workflow or graph transition;
- shared-context child execution;
- team/member collaboration;
- no natural equivalent.

Do not classify these as equivalent merely because all involve multiple agents.

If several mechanisms share a narrower common semantic, narrow or rename the specification to that semantic.

If they do not form a coherent semantic cluster, move `delegates` out of the portable core. Consider whether a weaker composition declaration such as `agents:` is the honest common abstraction.

A failed delegation mapping that exposes a false abstraction is a successful result.

## Other hypotheses to challenge

### `description`

Determine whether it is:

- passive metadata;
- model-visible routing information;
- delegation-tool description;
- UI discovery text;
- some combination.

Do not call these equivalent when their runtime effect differs materially.

### Agent Skills

Determine whether skills are:

- agent-private;
- runtime-global;
- project-global;
- eagerly injected;
- progressively disclosed.

Do not treat eager prompt injection as equivalent to Agent Skills progressive disclosure.

### Agent Plugins / MCP

Determine whether plugin capabilities remain owned by one agent or become ambient/global.

Test transport and configuration fidelity.

Do not treat generic tool registration as automatically equivalent to loading an Agent Plugin.

### Model requirements

Test whether capability-based requirements can be resolved cleanly without concrete model names in the portable source.

Distinguish objectively detectable capabilities from deployment-attested routing properties such as `reasoning`.

### Instructions

Determine whether the framework has a true persistent system/developer instruction mechanism or whether lowering merely prepends text to individual tasks.

Classify semantic differences honestly.

## Architecture

Keep the portable parser and semantic model target-neutral.

A target adapter should receive:

- the validated portable agent graph;
- target bindings/deployment configuration;
- the target runtime environment.

It should produce or instantiate:

- native framework agents;
- required target-native capability adapters;
- a compatibility report.

Avoid target-specific conditionals in the portable parser.

Keep target bindings outside the portable profile. Do not revive `x-<host>` sections or other in-document host extensions.

## Evidence requirements

For every target retain:

- pinned dependency versions;
- native/generated representation where useful;
- integration-test output;
- compatibility report;
- trace or structured observation showing multi-agent and capability behavior;
- known semantic losses.

Generate the consolidated compatibility matrix from individual reports. Do not maintain it manually.

For every proposed semantic, `EVIDENCE.md` must contain:

- observed native mechanisms by target;
- common semantic intersection;
- important differences;
- compatibility classifications;
- recommendation: `CORE`, `OPTIONAL`, `CONVENTION`, `HOST`, or `REMOVE`;
- rationale based on implementation evidence.

## Review the proposed profile after implementation

After all new runtime targets have been exercised, re-evaluate every current field.

A field belongs in the portable core only when there is convincing cross-framework semantic convergence.

Do not preserve a field merely because the current discussion draft contains it.

Specifically decide the status of:

- `name`
- `description`
- Markdown instructions
- `model.requires`
- `model.prefers`
- `skills`
- `plugins`
- `delegates`

The final specification revision must follow the evidence, not precede it.

## Deliverables

Produce:

1. executable adapters for all eight new runtime frameworks;
2. automated unit and integration tests;
3. pinned dependency definitions;
4. compatibility reports for every target;
5. a generated cross-target compatibility matrix, including the existing targets where their evidence remains valid;
6. the unchanged portable `research-team` fixture;
7. a concise `EVIDENCE.md` explaining what survived and what failed;
8. proposed modifications to the Agent Composition Profile based only on implementation evidence;
9. an updated discussion draft;
10. a concise external proposal suitable for the Agent Plugins community.

The concise external proposal must not present this as a new competing standard. Frame it as implementation evidence relevant to portable Agent Profiles and the existing Agent Plugins incubation effort.

## Success criterion

Success is not “all frameworks compile.”

Success is learning whether the same small agent declaration preserves materially the same agent across independent frameworks.

A failed mapping that exposes a false abstraction is a valuable result.
