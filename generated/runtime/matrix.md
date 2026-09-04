# Generated compatibility matrix

Evidence kind: agno=runtime, crewai=runtime, google-adk=runtime, langgraph=runtime, llamaindex=runtime, microsoft-agent-framework=runtime, openai-agents=runtime, pydantic-ai=runtime, amplifier=static-lowering, claude-code=static-lowering, codex=static-lowering, afm=static-lowering

## Entry-agent classification by source semantic

| semantic | agno | crewai | google-adk | langgraph | llamaindex | microsoft-agent-framework | openai-agents | pydantic-ai | amplifier | claude-code | codex | afm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| delegates | approximated | approximated | approximated | resolved | approximated | preserved | preserved | resolved | preserved | preserved | resolved | unsupported |
| description | approximated | approximated | preserved | resolved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| instructions | preserved | approximated | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| model.prefers.vision-input | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | resolved | resolved | resolved | resolved |
| model.requires.reasoning | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved |
| model.requires.tool-use | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved |
| name | preserved | approximated | resolved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| plugins | resolved | resolved | resolved | unsupported | unsupported | resolved | resolved | resolved | unsupported | resolved | resolved | resolved |
| plugins.activation | unverified | unverified | unverified | unverified | unverified | unverified | unverified | unverified | not-declared | not-declared | not-declared | not-declared |
| skills | preserved | preserved | resolved | resolved | resolved | preserved | resolved | resolved | unsupported | resolved | resolved | preserved |
| skills.durability | unverified | unverified | unverified | unverified | unverified | unverified | unverified | unverified | not-declared | not-declared | not-declared | not-declared |
| skills.resources | unverified | unverified | unverified | unverified | unverified | unverified | unverified | unverified | not-declared | not-declared | not-declared | not-declared |

## Strict conformance by module (all agents)

`accepted` means no finding in the module is approximated or unsupported; `unverified` findings do not block and are listed in each report.

| module | agno | crewai | google-adk | langgraph | llamaindex | microsoft-agent-framework | openai-agents | pydantic-ai | amplifier | claude-code | codex | afm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| core | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| delegates | rejected | rejected | rejected | accepted | rejected | accepted | accepted | accepted | accepted | accepted | accepted | rejected |
| description | rejected | rejected | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| model | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted |
| plugins | accepted | accepted | accepted | rejected | rejected | accepted | accepted | accepted | rejected | accepted | accepted | accepted |
| skills | accepted | accepted | accepted | accepted | accepted | accepted | accepted | accepted | rejected | accepted | accepted | accepted |

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

Generated from individual compatibility reports by `scripts/build_runtime_matrix.py`.
