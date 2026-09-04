# Generated compatibility matrix

Evidence kind: agno=runtime, crewai=runtime, google-adk=runtime, langgraph=runtime, llamaindex=runtime, microsoft-agent-framework=runtime, openai-agents=runtime, pydantic-ai=runtime, amplifier=static-lowering, claude-code=static-lowering, codex=static-lowering, afm=static-lowering

| semantic | agno | crewai | google-adk | langgraph | llamaindex | microsoft-agent-framework | openai-agents | pydantic-ai | amplifier | claude-code | codex | afm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| delegates | approximated | approximated | approximated | approximated | approximated | preserved | preserved | approximated | preserved | preserved | resolved | unsupported |
| description | approximated | approximated | preserved | unsupported | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| instructions | preserved | approximated | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| model.prefers.vision-input | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | omitted-preference | resolved | resolved | resolved | resolved |
| model.requires.reasoning | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved |
| model.requires.tool-use | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved | resolved |
| name | preserved | approximated | resolved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved | preserved |
| plugins | resolved | resolved | resolved | unsupported | unsupported | resolved | resolved | resolved | unsupported | resolved | resolved | resolved |
| skills | approximated | approximated | approximated | approximated | approximated | approximated | approximated | approximated | unsupported | resolved | resolved | preserved |

Generated from individual compatibility reports by `scripts/build_runtime_matrix.py`.
