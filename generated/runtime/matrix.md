# Generated compatibility matrix

Evidence kind: agno=runtime, crewai=runtime, google-adk=runtime, langgraph=runtime, llamaindex=runtime, microsoft-agent-framework=runtime, openai-agents=runtime, pydantic-ai=runtime, amplifier=product-static, claude-code=product-static, codex=product-static, copilot=product-static, opencode=product-static, afm=product-static

## Entry-agent classification by source semantic

| semantic | agno | crewai | google-adk | langgraph | llamaindex | microsoft-agent-framework | openai-agents | pydantic-ai | amplifier | claude-code | codex | copilot | opencode | afm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| description | approximated | approximated | preserved | resolved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| instructions | preserved | approximated | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| model.prefers.vision-input | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | resolved | resolved | resolved | resolved | resolved | resolved |
| model.requires.reasoning | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved |
| model.requires.tool-use | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved |
| name | preserved | approximated | resolved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | resolved | preserved |
| plugins | resolved | resolved | resolved | unsupported | unsupported | resolved | resolved | resolved | unsupported | resolved | resolved | resolved | resolved | resolved |
| plugins.activation | unverified | unverified | unverified | unverified | unverified | unverified | unverified | unverified | not-declared | not-declared | not-declared | not-declared | not-declared | not-declared |
| skills | preserved | preserved | resolved | resolved | resolved | preserved | resolved | resolved | unsupported | resolved | resolved | resolved | resolved | preserved |
| skills.durability | unverified | unverified | unverified | unverified | unverified | unverified | unverified | unverified | not-declared | not-declared | not-declared | not-declared | not-declared | not-declared |
| skills.resources | unverified | unverified | unverified | unverified | unverified | unverified | unverified | unverified | not-declared | not-declared | not-declared | not-declared | not-declared | not-declared |
| subagents | approximated | approximated | approximated | resolved | approximated | preserved | preserved | resolved | preserved | preserved | resolved | preserved | preserved | unsupported |

## Strict conformance by module (all agents)

`accepted` means no finding in the module is approximated or unsupported; `unverified` findings do not block and are listed in each report.

| module | agno | crewai | google-adk | langgraph | llamaindex | microsoft-agent-framework | openai-agents | pydantic-ai | amplifier | claude-code | codex | copilot | opencode | afm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| core | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| description | rejected | rejected | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| model | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| plugins | accepted | accepted | accepted | rejected | rejected | accepted | accepted | accepted | rejected | accepted | accepted | accepted | accepted | accepted |
| skills | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | rejected | accepted | accepted | accepted | accepted | accepted |
| subagents | rejected | rejected | rejected | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | rejected |

## Agent Plugin activation probe (runtime targets)

Fixture `examples/runtime-probes/plugin-activation`: one plugin, one stdio server spawned by the framework and one header-gated streamable HTTP server. `activated` means handshake, tool discovery, invocation, and a result reaching the agent runtime all succeeded.

| target | echostdio | echohttp | stdio cwd honored | stdio env honored | tool attribution |
| --- | --- | --- | --- | --- | --- |
| agno | activated | activated | true | true | by server name |
| crewai | activated | activated | false | true | CrewAI names MCP tools after the server command or URL |
| google-adk | activated | activated | true | true | by server name |
| langgraph | activated | activated | true | true | by server name |
| llamaindex | activated | activated | false | true | by server name |
| microsoft-agent-framework | activated | activated | true | true | by server name |
| openai-agents | activated | activated | true | true | by server name |
| pydantic-ai | activated | activated | true | true | by server name |

## Product probes (executed headless against a scripted model endpoint)

| product / fixture | version | instructions in system prompt | skills: catalog first, body on activation, persists | subagent: called, own instructions, result returned | MCP tools offered |
| --- | --- | --- | --- | --- | --- |
| claude-code/plugin-activation | 2.1.277 (Claude Code) | true | no skills in fixture | no subagents in fixture | mcp__echohttp__echo_http, mcp__echostdio__echo_stdio |
| claude-code/research-team | 2.1.277 (Claude Code) | true | true, true, true | explorer, true, true | none |

Generated from individual compatibility reports by `scripts/build_runtime_matrix.py`.
