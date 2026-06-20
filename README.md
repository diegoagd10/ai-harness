# ai-harness

Personal, version-controlled configuration for AI coding harnesses — one source
of truth, copied into the places Claude Code, GitHub Copilot CLI, and generic
`.agents` consumers expect.

## Why we built this

LLMs produce code fast, but the code they produce by default is generic. You
spend the real time in small "fix it" cycles: refine this function, extract that
helper, rename those variables, add error handling the model forgot. Each cycle
costs context, and after a few rounds the thread is too long for the model to
hold the whole design.

Tool choice amplifies the problem. Claude Code, Copilot CLI — each stores
configuration in a different place, with a different format, for a different
agent graph. Without a single source of truth, you duplicate skills and persona
rules across harnesses, then forget which copy is the canonical one.

**ai-harness** is our response. It gives you a single, version-controlled home
for your agent persona and skills, then copies everything into the right places
so every harness sees the same configuration.

## What this tool does

**ai-harness** is a persona + skills installer for AI coding agent CLIs. It
copies a bundled `AGENTS.md` (the persona) and a `skills/` directory into each
supported agent CLI's native config directory. You manage one set of files; the
tool distributes them everywhere they need to go.

Two commands:

- `ai-harness install` — copies AGENTS.md + skills into each agent CLI's config
  dir. Generic (`~/.agents/`) is always installed. The `-o` flag adds specific
  agent CLIs on top.
- `ai-harness uninstall` — removes exactly what `install` wrote, using a
  persisted manifest. Works even when the source repo is gone. No-args removes
  everything; `-o` removes only selected agent CLIs.

Reinstalling is byte-identical — running `install` again produces exactly the
same files, so downstream tools don't churn on unchanged content.

## Getting started

Requires Python >= 3.12.

```bash
git clone https://github.com/diegoagd10/ai-harness.git
cd ai-harness
uv tool install .              # puts ai-harness on PATH (~/.local/bin/ai-harness)
ai-harness install             # copies AGENTS.md + skills into ~/.agents/
```

If you prefer not to install on PATH, use `uv run` directly:

```bash
uv run ai-harness install
```

To remove everything the tool installed:

```bash
ai-harness uninstall
```

`ai-harness uninstall` removes only files listed in the manifest,
then removes the manifest. It does not need the source repo to be available.

### Prerequisite: Engram

For the system to work well, also install
[Engram](https://github.com/Gentleman-Programming/engram) — a persistent memory
MCP server. Engram is what lets the AI agents that consume `ai-harness` retain
context across sessions and survive context compactions. Without it, the
agents lose memory between sessions and start each one cold.

## What's in here

The project is a uv-managed Python package. The main regions of the tree:

- `src/ai_harness/` — the CLI package. The harness module owns the install/uninstall
  operations (path mapping, resource enumeration, manifest persistence); the commands
  module is a thin typer adapter over them.
- `src/ai_harness/resources/` — the bundled artifacts (`AGENTS.md` and `skills/`)
  that the installer copies into each agent CLI's home directory.
- `tests/` — Python unit tests for the CLI package. Run with `uv run pytest`.
- `e2e/` — end-to-end test suite and Docker sandbox (`e2e/docker-test.sh`).
- `docs/adr/` — architecture decision records.

The repo root also holds `pyproject.toml` (project metadata and dependencies) and
`tasks.py` (Invoke tasks for running the e2e suite).

## Supported agent CLIs

`ai-harness install` copies the same persona and skills into the native
configuration directories of every supported agent CLI:

| Agent CLI | Configuration home | Persona path |
|-----------|-------------------|--------------|
| Generic | `~/.agents/` | `~/.agents/AGENTS.md` |
| Claude Code | `~/.claude/` | `~/.claude/CLAUDE.md` |
| GitHub Copilot CLI | `~/.copilot/` | `~/.github/copilot-instructions.md` |

Generic is always installed. It provides the persona for any agent CLI
that reads from the standard `~/.agents/` directory.

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

# Run inside Docker (fully isolated):
e2e/docker-test.sh
```

## Contributing

- Run `uv run inv test` before opening a pull request.
- File issues at [https://github.com/diegoagd10/ai-harness/issues](https://github.com/diegoagd10/ai-harness/issues).
- Open pull requests against the same remote's `main` branch.
