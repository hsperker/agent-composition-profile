# Draft: Agent Plugins discussion post

> Draft for the Agent Plugins incubation discussion. Edit freely before posting. Repository: https://github.com/hsperker/agent-composition-profile

## We tested where an Agent Profile stops being portable. The answer is: early.

We investigated the Agent Profile idea by implementing a candidate profile across eight agent framework runtimes (LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, Microsoft Agent Framework) and four declarative targets (Amplifier, Claude Code, Codex, AFM). Every adapter builds native objects and runs them with deterministic models. Grades are reviewer judgments against the published Agent Skills, Agent Plugins, and MCP contracts, backed by tests, and untested properties are marked `unverified`.

The experiment did not support a general portable agent runtime abstraction. Model policy and generic multi-agent delegation did not converge. What survived was much smaller: logical identity, persistent agent instructions, and optional composition of Agent Skills and Agent Plugins.

What survived is small.

**Required:** `name` and a Markdown instruction body, applied on every invocation and kept distinct from task input. Seven of eight runtimes preserve both. CrewAI does not: its role, goal, and backstory template changes both, and its custom templates fix that only by collapsing the prompt into one user message.

**Optional, with one rule:** `description`, `skills`, `plugins`. If the field is present, a strict host preserves its defined semantics or rejects the profile. A skill or plugin reference means availability to the declaring agent, not isolation. Scoping stays with the host, as in Agent Plugins.

**Incubating:** `model.requires`. Declared by the author, resolved by the host. The concept held, but no capability vocabulary exists yet, so it stays out of the first proposal.

**Out:** model selection and preferences, delegation, orchestration, workflows, deployment. One generic `delegates` field hid six different mechanisms.

Two findings from the plugin probe are not obvious from reading the formats:

- **Native MCP support does not imply Agent Plugins support.** A plugin with a local MCP echo server activated in all eight runtimes over stdio and header gated streamable HTTP. But CrewAI and LlamaIndex cannot set a working directory through their MCP APIs, so they cannot honor the plugin root default in §7.2.1. No SDK expands `${PLUGIN_ROOT}` or provides the reserved variables either; the host has to.
- **Agent Plugin portability does not imply stable model visible tool names.** The same tool appeared as `echo_stdio`, `echostdio_echo_stdio`, and a truncated hash across runtimes. A plugin reference guarantees composition, not a tool identifier an instruction can rely on. This matches Agent Plugins' own stance that presentation is a host decision.

Also: every runtime activates Agent Skills through the dedicated tool pattern in the integration guide. We verified catalog disclosure and activation, not behavior under compaction or bundled resources.

The evidence, adapters, locks, and generated matrix are in the repository. We are not proposing a new standard. Our question is whether this small surviving intersection is enough to justify the Agent Profile component already being discussed here.
