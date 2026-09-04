# Agent Composition Profile Runtime Interoperability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Falsify or substantiate each proposed Agent Composition Profile semantic by constructing and running native agents in eight independent frameworks and deriving the revised proposal from recorded observations.

**Architecture:** The existing parser remains target-neutral and unchanged in responsibility. A new optional runtime layer receives the parsed `Package`, an external binding, and a framework environment; it lazily imports one SDK, constructs native agents, runs deterministic framework-owned loops where available, and emits normalized observations plus compatibility findings. Evidence generation consumes only the per-target reports and traces, so the matrix and recommendations cannot drift from the experiments.

**Tech Stack:** Python 3.13; pytest; PyYAML; jsonschema; LangChain 1.4.0; LangGraph 1.2.11; CrewAI 1.15.18; LlamaIndex Core 0.14.24; Agno 3.0.5; OpenAI Agents SDK 0.22.0; Google ADK 2.8.0; PydanticAI 2.38.0; Microsoft Agent Framework 1.17.0.

**Spec:** `CODEX-PROMPT.md`

## Global Constraints

- Keep `examples/research-team/**` byte-for-byte unchanged across every target.
- Use exact pins for every tested direct SDK dependency and retain a resolved lock file.
- Construct real native agent objects and invoke native framework runtime entry points wherever deterministic execution is possible.
- Do not use paid or remote inference in the default verification suite.
- Record `name`, `description`, `instructions`, every `model.requires` and `model.prefers` capability, `skills`, `plugins`, and `delegates` separately.
- Use only `preserved`, `resolved`, `approximated`, `unsupported`, and `omitted-preference` as mapping statuses.
- Strict mode rejects every required `approximated` or `unsupported` finding.
- Treat bounded task delegation, agent-as-tool, handoff, graph transition, shared-context execution, and team collaboration as different mechanisms.
- Derive the compatibility matrix from individual machine-readable reports; never edit it by hand.
- Revise the discussion draft only after all eight runtime experiments have produced evidence.

---

### Task 1: Normalize semantic findings and runtime observations

**Files:**
- Modify: `compiler/src/agent_profile_compiler/model.py`
- Modify: `compiler/src/agent_profile_compiler/report.py`
- Create: `compiler/src/agent_profile_compiler/runtime/model.py`
- Create: `compiler/src/agent_profile_compiler/runtime/common.py`
- Create: `compiler/tests/runtime/test_contract.py`

**Interfaces:**
- Consumes: `Package`, `Agent`, `Skill`, `Plugin`, and `CompatibilityReport` from the static compiler.
- Produces: `RuntimeObservation(kind, agent, data)`, `RuntimeArtifact(native_agents, report, observations)`, and helpers that report each source semantic independently.

- [ ] Write failing tests proving `name` and `description` are separate findings, strict mode blocks required approximations, preferences may be omitted, and JSON observations are deterministic.
- [ ] Run `pytest compiler/tests/runtime/test_contract.py -q` and verify failures are caused by the missing runtime contract.
- [ ] Implement the frozen observation/artifact types, semantic-report helpers, and strict validation with the five allowed statuses.
- [ ] Run the focused tests and the existing static suite; keep both green.
- [ ] Commit the contract independently if repository history is being retained.

### Task 2: Pin and isolate the eight SDK surfaces

**Files:**
- Modify: `compiler/pyproject.toml`
- Create: `compiler/uv.lock`
- Create: `compiler/src/agent_profile_compiler/runtime/registry.py`
- Create: `compiler/tests/runtime/test_registry.py`

**Interfaces:**
- Consumes: target name and runtime extra installation.
- Produces: `load_runtime_adapter(target: str) -> RuntimeAdapter` using lazy imports so one missing SDK cannot break unrelated compiler commands.

- [ ] Write a failing registry test for all eight canonical target names and an actionable missing-extra error.
- [ ] Add exact direct dependency pins and build the lock using the current stable versions listed in the plan header.
- [ ] Implement lazy module resolution without importing SDKs at package import time.
- [ ] Install the locked runtime environment and run import smoke tests for every SDK.
- [ ] Record the Python and direct SDK versions in a generated environment manifest.

### Task 3: Progressive-disclosure and MCP capability adapters

**Files:**
- Create: `compiler/src/agent_profile_compiler/runtime/skills.py`
- Create: `compiler/src/agent_profile_compiler/runtime/plugins.py`
- Create: `examples/runtime-mcp/**`
- Create: `compiler/tests/runtime/test_capabilities.py`

**Interfaces:**
- Produces: per-agent `SkillCatalog` whose metadata is discoverable before activation and whose body is read only by `activate(name)`; `PluginRuntime` preserving server transport/config and owner agent; framework tool factories consume these objects.

- [ ] Write failing tests proving skill instructions are absent before activation, become available only after activation, and never leak to another agent.
- [ ] Write failing tests for MCP owner scope, transport/config fidelity, explicit startup failure, and unavailable required tool-use.
- [ ] Add the smallest local stdio MCP fixture needed to exercise a live handshake; document why the unchanged remote fixture cannot do so.
- [ ] Implement the catalogs and plugin lifecycle without injecting skill bodies into initial instructions.
- [ ] Run focused tests and retain structured activation/handshake observations.

### Task 4: LangChain/LangGraph and CrewAI experiments

**Files:**
- Create: `compiler/src/agent_profile_compiler/runtime/langgraph.py`
- Create: `compiler/src/agent_profile_compiler/runtime/crewai.py`
- Create: `compiler/tests/runtime/test_langgraph_runtime.py`
- Create: `compiler/tests/runtime/test_crewai_runtime.py`

**Interfaces:**
- Each module implements `build(package, binding, strict) -> RuntimeArtifact` and `run(artifact, task) -> RuntimeRun`.

- [ ] Write failing native-object tests for identity, persistent instructions, bound model object, agent-private tools, and specialist relationships.
- [ ] Write failing runtime tests using framework-compatible deterministic models that force skill activation, MCP/tool execution, and one specialist invocation.
- [ ] Assert that LangGraph agent-as-tool and CrewAI crew/delegation traces are classified by their actual control/context semantics rather than a shared label.
- [ ] Implement only the native mechanisms exposed by each SDK and record every loss.
- [ ] Add negative tests for missing model attestations, broadened capability scope, and unavailable delegates; verify strict rejection.

### Task 5: LlamaIndex and Agno experiments

**Files:**
- Create: `compiler/src/agent_profile_compiler/runtime/llamaindex.py`
- Create: `compiler/src/agent_profile_compiler/runtime/agno.py`
- Create: `compiler/tests/runtime/test_llamaindex_runtime.py`
- Create: `compiler/tests/runtime/test_agno_runtime.py`

**Interfaces:**
- Implements the shared build/run contract and emits native workflow/team events.

- [ ] Write failing tests for native `FunctionAgent`/workflow and `Agent`/`Team` construction using exact SDK APIs.
- [ ] Execute deterministic native runtimes and capture active-agent, tool, member, result, and context observations.
- [ ] Test whether specialist instructions and capability sets are isolated or shared.
- [ ] Classify workflow handoff and team collaboration independently from bounded task delegation.
- [ ] Add strict negative tests for every required semantic that is only approximated or unsupported.

### Task 6: OpenAI Agents SDK and Google ADK experiments

**Files:**
- Create: `compiler/src/agent_profile_compiler/runtime/openai_agents.py`
- Create: `compiler/src/agent_profile_compiler/runtime/google_adk.py`
- Create: `compiler/tests/runtime/test_openai_agents_runtime.py`
- Create: `compiler/tests/runtime/test_google_adk_runtime.py`

**Interfaces:**
- Uses official deterministic/scripted model utilities when supplied by the SDK; implements the shared build/run contract.

- [ ] Write failing tests for native agents, persistent instructions, agent-scoped MCP/tool objects, and specialist exposure.
- [ ] For OpenAI, use `Agent.as_tool()` rather than handoff because the source requires bounded return-to-parent behavior; add a negative comparison proving handoff changes control semantics.
- [ ] For ADK, run the native runner with an `AgentTool` or sub-agent mechanism and record whether session/context sharing changes the source meaning.
- [ ] Exercise each runtime with deterministic tool and specialist call sequences.
- [ ] Add model-capability and plugin-startup failures and verify strict rejection.

### Task 7: PydanticAI and Microsoft Agent Framework experiments

**Files:**
- Create: `compiler/src/agent_profile_compiler/runtime/pydantic_ai.py`
- Create: `compiler/src/agent_profile_compiler/runtime/microsoft_agent_framework.py`
- Create: `compiler/tests/runtime/test_pydantic_ai_runtime.py`
- Create: `compiler/tests/runtime/test_microsoft_runtime.py`

**Interfaces:**
- Uses PydanticAI `TestModel`/`FunctionModel` and the Microsoft framework's official mock chat client where available; implements the shared build/run contract.

- [ ] Write failing tests for native object identity, instruction placement, model injection, tools, MCP, and specialist relationships.
- [ ] Execute the native agent loops and capture request messages, tool calls, specialist instructions, and returned control.
- [ ] Distinguish framework-native agent-as-tool support from an application-authored wrapper and classify accordingly.
- [ ] Add isolation and missing-capability negative tests with strict-mode assertions.
- [ ] Run all eight runtime suites together to detect dependency or global-state interference.

### Task 8: Evidence generation

**Files:**
- Create: `compiler/src/agent_profile_compiler/runtime/evidence.py`
- Create: `scripts/run_runtime_evidence.py`
- Create: `compiler/tests/runtime/test_evidence_generation.py`
- Generate: `evidence/<target>/environment.json`
- Generate: `evidence/<target>/native.json`
- Generate: `evidence/<target>/observations.json`
- Generate: `evidence/<target>/compatibility-report.json`
- Generate: `evidence/compatibility-matrix.json`
- Generate: `evidence/compatibility-matrix.md`

**Interfaces:**
- Consumes only `RuntimeArtifact` and `RuntimeRun` serialization.
- Produces reproducible per-target evidence and a matrix with one row per source semantic and target.

- [ ] Write a failing test that changes one report and proves both generated matrix formats change from that input.
- [ ] Implement deterministic evidence serialization and matrix generation with no manual status table.
- [ ] Run every model-independent experiment and preserve stdout/test output plus structured traces.
- [ ] Mark remote/paid inference checks separately and never imply they ran when credentials are absent.
- [ ] Verify every target has exact versions, native representation, observations, known losses, and a report matching the observations.

### Task 9: Evidence-led profile revision

**Files:**
- Create: `EVIDENCE.md`
- Modify: `spec/agent-composition-profile-v0.1-discussion-draft.md`
- Modify: `spec/agent-composition-profile-v0.1-frontmatter.schema.json` only if supported by the experiments.
- Create: `EXTERNAL-PROPOSAL.md`
- Modify: `README.md`

**Interfaces:**
- Consumes generated evidence; produces human recommendations `CORE`, `OPTIONAL`, `CONVENTION`, `HOST`, or `REMOVE` for every proposed field.

- [ ] For each semantic, summarize observed native mechanisms, the coherent intersection, decisive differences, statuses, and a non-majoritarian recommendation.
- [ ] Decide explicitly whether `delegates` narrows to a weaker composition declaration or leaves the portable core.
- [ ] Decide skill scope/progressive disclosure, plugin/MCP ownership, description effects, instruction persistence, and model-capability requirements from traces.
- [ ] Revise the discussion draft only where the evidence warrants it and retain failed mappings as first-class results.
- [ ] Write a concise Agent Plugins incubation contribution, explicitly not a competing standard.

### Task 10: Final verification and adversarial audit

**Files:**
- Modify: `scripts/verify.sh`
- Modify: `scripts/verify_generated.py`
- Modify: any faulty implementation or evidence file uncovered by verification.

**Interfaces:**
- Produces one local command that verifies static lowering, eight native runtime suites, regenerated evidence, and documentation consistency.

- [ ] Run every focused test, the complete pytest suite, compile checks, and generated-artifact validation from a clean process.
- [ ] Regenerate evidence and fail if `git diff --exit-code` shows stale generated outputs.
- [ ] Check the unchanged research fixture against its imported hashes.
- [ ] Audit every `preserved`/`resolved` claim against a corresponding runtime observation; downgrade unsupported claims.
- [ ] Run `git diff --check` and report exact verification commands, versions, skipped remote tests, and remaining limitations.
