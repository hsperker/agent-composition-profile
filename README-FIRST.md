# Agent Composition Profile — Codex Handoff

Start with `CODEX-PROMPT.md`.

## Inputs

- `agent-composition-profile-v0.1-discussion-draft.md` — current research/specification draft. Treat every proposed semantic as provisional.
- `agent-composition-profile-v0.1-frontmatter.schema.json` — companion schema for the current draft.
- `agent-composition-profile-lowering-walkthrough.md` — explanation of the existing static lowering work.
- `agent-composition-profile-implementation-report.md` — evidence and limitations from the current proof of concept.
- `agent-composition-profile-poc.zip` — reference compiler, fixtures, tests, bindings, and generated outputs for Amplifier, Claude Code, Codex, and WSO2 AFM.
- `CODEX-PROMPT.md` — task brief for the next validation round.

## Important status

The existing compiler provides tested static lowering evidence. It has **not** yet established end-to-end runtime interoperability in the target frameworks.

The next task is empirical: implement real runtime adapters, try to falsify the proposed abstraction, and revise the profile only from evidence.
