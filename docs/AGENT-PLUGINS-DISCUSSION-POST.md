# Draft: Agent Plugins discussion post

> Draft for the Agent Plugins incubation discussion. Edit freely before posting. Repository: https://github.com/hsperker/agent-profile

## We compiled one Agent Profile into Claude Code, Codex, Copilot CLI, and OpenCode and ran it. Here is what survived.

A portable Agent Profile must lower into the tools people run agents in. Otherwise it is a schema. We took that as the test and built a candidate profile, a reference compiler, and a probe harness that runs the compiled project headless in each product against a scripted model endpoint and records what the model saw.

Two dimensions. Products first, because they make ownership real: whoever holds the file can leave the host that produced it. Claude Code 2.1.277, Codex 0.154.0, GitHub Copilot CLI 1.0.88, and OpenCode 1.18.32 and 2.0.14 were executed. Amplifier and AFM were lowered and checked. Then eight agent frameworks (LangGraph, CrewAI, LlamaIndex, Agno, OpenAI Agents SDK, Google ADK, PydanticAI, Microsoft Agent Framework) as canaries for the semantics, executed with deterministic models. Grades are reviewer judgments against the published Agent Skills, Agent Plugins, and MCP contracts, backed by tests. Anything not exercised is `unverified`.

What survived is small, and every product runs it.

**Required:** `name` and a Markdown instruction body, applied on every invocation and kept distinct from task input. Every product and seven of eight frameworks carry both. Codex delivers the body as a persistent `AGENTS.md` message rather than a system prompt; that still counts. CrewAI does not: its role, goal, and backstory template fuses identity, description, and instructions.

**Optional, one rule:** `description`, `skills`, `plugins`. If present, a strict host preserves the field's defined semantics or rejects the profile. A reference means availability to the agent, not isolation; every product lists its own ambient skills beside the profile's.

**Optional, narrowly typed:** `subagents`. Generic delegation hid six mechanisms behind one word and is gone. What survives is the relation all four executed products implement: a listed agent invoked as a bounded task with its own instructions, returning a result while the caller keeps control. Additive, like skills and plugins.

**Incubating:** `model.requires`. Declared by the author, resolved by the host. The concept held; no capability vocabulary exists yet.

**Out:** model selection and preferences, handoffs, workflows, teams, orchestration beyond bounded calls, deployment.

Four things the product probes showed that reading the formats does not:

- **Skill activation converges, skill tooling does not.** All four products advertise the catalog first and inject the body on activation, as the Agent Skills integration guide describes. Claude Code and Copilot use a `skill` tool, OpenCode renamed its argument between major versions, Codex has no tool and the model reads `SKILL.md` from disk. A profile can rely on the pattern, not on a tool.
- **The subagent list is a catalog in two products and an allowlist in two.** Claude Code and OpenCode enforce the list. Codex and Copilot CLI emit it, then advertise every agent in the project and run one the list omits. The profile therefore says which agents must be available and leaves exclusivity to the host.
- **Native MCP support does not imply Agent Plugins support.** The same plugin, one stdio server and one header gated streamable HTTP server, activated in all eight frameworks and in Claude Code, Codex, Copilot CLI, and OpenCode 1.18.32. But Claude Code, Copilot, CrewAI, and LlamaIndex cannot set a working directory, so they cannot honor the plugin root default in §7.2.1, and no host expands `${PLUGIN_ROOT}` or supplies the reserved variables; the compiler had to. Codex starts servers in the background and a slow one misses the first turn. OpenCode 2.0.14 connected both servers and offered the model neither tool.
- **Tool names are not portable.** The same echo tool reached the model as `mcp__echostdio__echo_stdio`, `echostdio_echo_stdio`, `echostdio-echo_stdio`, a namespaced `echo_stdio`, and a truncated hash. A plugin reference guarantees composition, not an identifier an instruction can name.

One product changed three things a compiler depends on across one major version: subagent tool name, skill tool argument, MCP exposure. Product evidence has to be reprobed per release, and the harness does that in one command.

The compiler, probes, locked environments, per product evidence, and the generated matrix are in the repository. We are not proposing a new standard. Our question for this group is whether this intersection, small but executable in every product we could run, is the right scope for the Agent Profile component already under discussion.
