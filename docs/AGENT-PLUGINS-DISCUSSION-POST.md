# Draft: Agent Plugins discussion post

> Draft for the Agent Plugins incubation discussion. Edit freely before posting. Repository: https://github.com/hsperker/agent-composition-profile

## Where does an Agent Profile actually stop being portable? We tested it.

Agent Plugins v1 leaves agents out because their formats have not converged. We wanted to know how far they have converged, so we tested a candidate profile against eight framework runtimes (LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, Microsoft Agent Framework) and four declarative formats (Amplifier, Claude Code, Codex, AFM). Every adapter builds native objects, runs them with deterministic models, and grades each field against the published Agent Skills, Agent Plugins, and MCP contracts. Grades are reviewer judgments backed by tests, not measurements, and untested properties are marked `unverified`.

What survived is small.

**Required:** `name` and a Markdown instruction body. Seven of eight runtimes preserve both. CrewAI does not: its role, goal, and backstory template changes both, and its custom templates fix that only by collapsing the prompt into one user message.

**Optional, with one rule:** `description`, `skills`, `plugins`. If the field is present, a strict host preserves its defined semantics or rejects the profile. A skill or plugin reference means availability to the declaring agent, not isolation. Scoping stays with the host, as in Agent Plugins.

**Incubating:** `model.requires`. Declared by the author, resolved by the host. The concept held, but no capability vocabulary exists yet, so it stays out of the first proposal.

**Out:** model selection and preferences, delegation, orchestration, workflows, deployment. One generic `delegates` field hid six different mechanisms.

Findings we did not expect:

- A plugin with a local MCP echo server activated in all eight runtimes over stdio and header gated streamable HTTP. But two SDKs cannot set a working directory, so they cannot honor the plugin root default in §7.2.1. Native MCP support is not Agent Plugins support.
- No SDK expands `${PLUGIN_ROOT}` or provides the reserved variables. The host adapter has to.
- The tool name a model sees is not portable. The same tool appeared as `echo_stdio`, `echostdio_echo_stdio`, and a truncated hash. A plugin reference guarantees composition, not a stable tool identifier.
- Every runtime activates Agent Skills through the dedicated tool pattern in the integration guide. None was tested for durability under compaction.

The evidence, adapters, locks, and generated matrix are in the repository. We are not proposing a new standard. We are asking whether this shape is the right starting point for the Agent Profile discussion here.
