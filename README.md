# ai-harness

Personal, version-controlled configuration for AI coding harnesses — one source
of truth, copied into the places OpenCode, Claude Code, and generic `.agents`
consumers expect.

## Why we built this

LLMs produce code fast, but the code they produce by default is generic. You
spend the real time in small "fix it" cycles: refine this function, extract that
helper, rename those variables, add error handling the model forgot. Each cycle
costs context, and after a few rounds the thread is too long for the model to
hold the whole design.

Planning usually lives in chat history. Chat history is ephemeral — it scrolls
away, it gets compacted, it disappears when the session ends. There is no
artifact that says "this is what we decided and why." Without that artifact,
every new session starts from scratch, or worse, from a stale mental model of
what the last person intended.

Tool choice amplifies the problem. OpenCode, Claude Code, Copilot — each stores
configuration in a different place, with a different format, for a different
agent graph. Without a single source of truth, you duplicate skills, prompts, and
rules across harnesses, then forget which copy is the canonical one.

**ai-harness** is our response to all three problems. It gives you a
single, version-controlled home for your agent persona, skills, and Spec-Driven
Development pipeline, then copies everything into the right places so every
harness sees the same configuration.

## What this tool does

**ai-harness** drives a planning-first SDD (Spec-Driven Development)
workflow where every change starts as a structured proposal, spec, design, and
task list before any code is written. Instead of asking the LLM to write code
immediately, the orchestrator walks through structured phases: explore the
codebase, write a proposal with acceptance criteria, produce specs and a design,
decompose into bounded tasks, then implement each task through strict TDD.

The pipeline runs entirely through prompts and configuration — there is no custom
runtime and no extra daemon.

```
sdd-orchestrator (primary)
  └─ task tool ─▶ sdd-init → sdd-explore → sdd-propose ─┬─▶ sdd-spec ─┐
                                                        └─▶ sdd-design ┴─▶ sdd-tasks
                  ─▶ sdd-apply → sdd-verify → sdd-archive
  judgment ─▶ jd-judge-a ∥ jd-judge-b (blind, parallel) → jd-fix-agent → re-judge
  review   ─▶ review-risk / -readability / -reliability / -resilience (R1–R4)
```

The orchestrator never works inline. It asks a session preflight (interactive vs
auto, artifact backend, PR strategy, review budget), enforces hard gates between
phases, and applies a review-workload guard before implementing anything. The
result is implementation that stays inside bounded tasks rather than sprawling
across the codebase.

## Getting started

Requires Python >= 3.12.

```bash
git clone https://github.com/diegoagd10/ai-harness.git
cd ai-harness
uv tool install .              # puts ai-harness on PATH (~/.local/bin/ai-harness)
ai-harness install             # copies AGENTS.md, skills, opencode.json, SDD prompts into home dirs
```

If you prefer not to install on PATH, use `uv run` directly:

```bash
uv run ai-harness install
```

To remove everything the tool installed:

```bash
ai-harness uninstall
```

`ai-harness uninstall` removes only files listed in the central harness manifest,
then removes the manifest. It does not need the source repo to be available.

## Driving the SDD pipeline

`ai-harness` is a single Python binary. It was built **on top of**
[OpenSpec](https://github.com/Fission-AI/OpenSpec) — it adopts the same
spec-driven change format (proposal, specs, design, tasks) — but it does **not**
depend on the OpenSpec CLI. The pipeline is implemented natively inside
`ai-harness` and is driven from the command line by two subcommands:

- `sdd-status` — reports the current SDD phase state for an active change.
  Invoke it as `ai-harness sdd-status` (it emits machine-readable JSON).
- `sdd-continue` — shows the next SDD action and the per-phase instructions the
  orchestrator needs to keep the pipeline moving. Invoke it as
  `ai-harness sdd-continue`.

To use them in a new project, copy the starter config and customize it:

```bash
cp templates/openspec/config.yaml openspec/config.yaml
```

The config lets you define project rules for each SDD artifact and pin the
testing commands the pipeline uses.

### Prerequisite: Engram

For the system to work well, also install
[Engram](https://github.com/Gentleman-Programming/engram) — a persistent memory
MCP server. Engram is what lets the AI agents that consume `ai-harness` retain
context across sessions and survive context compactions. Without it, the
orchestrator loses memory between sessions and starts each one cold.

## What's in here

The project is a uv-managed Python package. The main regions of the tree:

- `src/ai_harness/` — the CLI package. Each `ai-harness` subcommand (`install`, `uninstall`, `sdd-status`, `sdd-continue`) is implemented in its own subpackage; per-CLI installers under `src/ai_harness/artifacts/installers/` decide which bundled resources get installed for which target harness.
- `src/ai_harness/resources/` — the bundled artifacts (skills, prompts, agent configs, project config templates) that the installers copy into each AI harness's home directory. The CLI does NOT install this directory verbatim; the per-CLI installers enumerate the specific files they own.
- `tests/` — Python unit tests for the CLI package. Run with `uv run pytest`.
- `e2e/` — end-to-end test suite and Docker sandbox (`e2e/docker-test.sh`).
- `openspec/` — spec-driven change artifacts for this project (`config.yaml`, `specs/`, `changes/`). The directory follows the OpenSpec spec format; the CLI implements the pipeline natively.

The repo root also holds `pyproject.toml` (project metadata and dependencies) and `tasks.py` (Invoke tasks for running the e2e suite). For everything else, explore the tree.

## Supported AI harnesses

`ai-harness install` copies the same persona, skills, and SDD prompts into the
native configuration directories of every supported harness:

| Harness | Configuration home | Adapter narrative |
|---------|-------------------|-------------------|
| OpenCode | `~/.config/opencode/` | `src/ai_harness/resources/agent-clis/opencode/` |
| Claude Code | `~/.claude/` | `src/ai_harness/resources/agent-clis/claude/` |
| GitHub Copilot CLI | `~/.copilot/` | [`docs/agents/copilot/README.md`](docs/agents/copilot/README.md) |

## Running tests

Unit tests run against the Python source (no Docker needed):

```bash
uv run pytest
```

End-to-end tests run the installed `ai-harness` binary inside isolated sandboxes:

```bash
# Run the full e2e suite locally (all sandboxed — zero host-side effects):
uv run inv test

# Run a single category in isolation:
uv run inv install
uv run inv uninstall
uv run inv sdd-status
uv run inv sdd-continue
uv run inv tool-lifecycle

# Run inside Docker (fully isolated):
e2e/docker-test.sh
```

## Contributing

- Run `uv run inv test` before opening a pull request.
- File issues at [https://github.com/diegoagd10/ai-harness/issues](https://github.com/diegoagd10/ai-harness/issues).
- Open pull requests against the same remote's `main` branch.
