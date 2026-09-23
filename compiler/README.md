# Agent Profile compiler

Lowers an Agent Profile package into the project layout of a product that reads agent files: Claude Code, Codex, GitHub Copilot, OpenCode, Amplifier, or AFM. Every run also writes a compatibility report that says, per agent and per field, whether the product preserves the field's meaning, resolves it another way, or cannot carry it.

## Install

Python 3.11 or newer. From this directory:

```bash
uv sync --extra test        # or: pip install -e ".[test]"
```

This installs the `agent-profile` command. Without installing, run `PYTHONPATH=src python -m agent_profile_compiler.cli` instead.

## Compile a package

```bash
agent-profile examples/subagents/lead.agent.md \
  --package-root examples/subagents \
  --target claude-code \
  --binding examples/bindings.yaml \
  --output out/claude-code
```

- `entry` is the agent document the host should run. Agents it lists under `subagents` are compiled too, recursively.
- `--package-root` is the directory that relative paths in the documents resolve against. The entry must be inside it.
- `--target` is one of `claude-code`, `codex`, `copilot`, `opencode`, `amplifier`, `afm`.
- `--binding` supplies what the product needs but the profile must not contain: model aliases, capability attestations, entry mode. See below.
- `--output` receives the product's files plus `compatibility-report.json`.

Exit code 0 means every field was preserved or resolved. Exit code 2 means the parser rejected the package or strict compilation would lose a field; the reason is printed and nothing is written. Add `--diagnostic` to write the files anyway and read the losses from the report.

Then open the output directory in the product. The generated files sit where the product looks for them, for example `.claude/agents/` and `.claude/skills/` for Claude Code, so the output can be the project itself.

## What the output looks like

| Target | Agents | Skills | MCP servers | Subagents |
|---|---|---|---|---|
| `claude-code` | `.claude/agents/<name>.md` | `.claude/skills/` | `mcpServers` in the agent file | `Agent(a, b)` in `tools` |
| `codex` | `.codex/agents/<name>.toml`, plus `AGENTS.md` for the entry in main mode | `.agents/skills/` | per agent `mcp_servers`, and `.codex/config.toml` for the entry | catalog note in the instructions |
| `copilot` | `.github/agents/<name>.agent.md` | `.github/skills/` | `mcp-servers` in the agent file, `.vscode/mcp.json` for VS Code | `agents` list |
| `opencode` | `.opencode/agent/<name>.md` | `.opencode/skills/` | `mcp` in `opencode.json` | `permission.task` map |

Every product needs the project marked trusted before it loads agents, skills, or MCP servers. That is a host setting, not something the compiler can write.

## Bindings

A binding is a YAML mapping for one target, or a `targets:` map keyed by target name. `examples/bindings.yaml` shows the keys the product targets read:

```yaml
targets:
  claude-code:
    capabilities: {tool-use: true}   # attests the profile's model.requires
    model: sonnet                    # product specific alias, never in the profile
    entry_mode: main                 # entry runs as the main agent; `subagent` otherwise
```

`capabilities` is how a deployment answers `model.requires`. A required capability the binding does not attest is reported as `unsupported`, and strict mode refuses.

## Reading the report

`compatibility-report.json` lists one finding per agent and field with a status and a reason:

- `preserved`: the product has a native mechanism with the same meaning.
- `resolved`: carried with a documented difference, such as a project wide skill catalog instead of a per agent one.
- `approximated` and `unsupported`: the meaning is changed or lost. Strict mode refuses both.
- `unverified`: representable but not exercised; listed, never blocking.

The `modules` section rolls findings up to the core (name and instructions) and each optional field, so a reader sees which field a product cannot carry without reading every finding.

## Examples

Three packages under `examples/`, all in draft 0.2 form. A test compiles each one strictly for the four executed products.

- `minimal/`: name and instructions, the required core and nothing else. Compiles to a single agent file everywhere.
- `skills-and-plugin/`: one Agent Skills directory and one Agent Plugin whose MCP server is the public Microsoft Learn server (`https://learn.microsoft.com/api/mcp`, streamable HTTP, no authentication), so the compiled agent can be run for real. Stdio servers are deliberately absent: Claude Code and Copilot cannot set a working directory for them, so they compile as `unsupported` there.
- `subagents/`: a lead with two leaf agents. Claude Code and OpenCode enforce the list; Codex and Copilot CLI expose the whole project catalog.

The repository's `examples/research-team/` is the evidence fixture and uses the draft 0.1 spelling (`delegates`); the parser accepts it as an alias. The packages here are the ones to copy from.

## Layout

```text
src/agent_profile_compiler/parser.py     package loader and validation
src/agent_profile_compiler/compiler.py   strict and diagnostic compilation
src/agent_profile_compiler/targets/      one module per product
src/agent_profile_compiler/report.py     compatibility report
src/agent_profile_compiler/runtime/      framework adapters, executed by the runtime tests
src/agent_profile_compiler/products/     headless product probes and scripted model endpoints
tests/                                   parser, targets, examples; runtime and product tests need their own environments
runtime-requirements/                    hash locked environments per framework and for the probes
```

Run `pytest` here for the parser, target, and example tests. The runtime and product tests are driven by the scripts in the repository root, because each needs a locked environment or an installed product.
