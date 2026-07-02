# ai-harness

Personal, version-controlled configuration for AI coding harnesses — one source
of truth, copied into the places Claude Code, GitHub Copilot CLI, OpenCode, and generic
`.agents` consumers expect.

## Why we built this

LLMs produce code fast, but the code they produce by default is generic. You
spend the real time in small "fix it" cycles: refine this function, extract that
helper, rename those variables, add error handling the model forgot. Each cycle
costs context, and after a few rounds the thread is too long for the model to
hold the whole design.

Tool choice amplifies the problem. Claude Code, Copilot CLI, OpenCode — each stores
configuration in a different place, with a different format, for a different
agent graph. Without a single source of truth, you duplicate skills and persona
rules across harnesses, then forget which copy is the canonical one.

**ai-harness** is our response. It gives you a single, version-controlled home
for your agent persona and skills, then copies everything into the right places
so every harness sees the same configuration.

## Prerequisites

ai-harness requires two external, globally-installed tools that it deliberately
does not own or provision (see [ADR 0006](docs/adr/0006-prereqs-not-owned-by-install.md)).
These are **Prerequisites** — shared across every repository on your machine.

### Engram (persistent memory)

[Engram](https://github.com/Gentleman-Programming/engram) is a persistent memory
MCP server that lets AI agents retain context across sessions and survive
compactions. Without it, agents lose memory between sessions and start each one
cold.

Engram setup is documented in its own repository:

- **OpenCode**: configure Engram as an MCP server — see the Engram repository for
  the current MCP configuration.
- **Claude Code**: install the Engram plugin — see the Engram repository for the
  current plugin setup steps.

Commands are not duplicated here because they evolve upstream; always follow the
Engram repository's own instructions.

### Matt Pocock engineering skills

The [matt-pocock skills](https://github.com/mattpocock/skills) provide the
engineering workflow skills (`setup-matt-pocock-skills`, `grill-with-docs`,
`to-prd`, `to-issues`). Install them once per machine with the `skills` CLI:

```bash
pnpm dlx skills install
```

This reads `skills-lock.json` and installs for both Claude Code and the generic
agents home (`~/.agents/skills/`). OpenCode reads skills from the generic agents
home, so one install covers both.

## What this tool does

**ai-harness** is a persona, skills, and change-agent installer for AI coding
Agent CLIs. It copies a bundled `AGENTS.md` (the persona) and a `skills/`
directory into each supported Agent CLI's native config directory, and renders
the change agents (`change-agent/`) for CLIs with native agent support (Claude
Code and OpenCode). You manage one set of files; the tool distributes them
everywhere they need to go.

Five commands:

- `ai-harness init` — **repo-local** scaffolding. Run inside a consuming
  repository to create the artifacts the skill flow assumes at the repo root: a
  `CODING_STANDARDS.md` skeleton and a labels-policy block in the repo's agent
  doc. Idempotent — never clobbers human-edited content. Distinct from
  `install`, which distributes the harness globally into each Agent CLI's `$HOME`
  config.

- `ai-harness install` — **global** distribution. Copies `AGENTS.md` + skills
  into each Agent CLI's config dir, and renders the change agents into the native
  agent directories of Claude Code and OpenCode. Generic (`~/.agents/`) is always
  installed. The `-o` flag adds specific Agent CLIs on top. Reinstalling is
  byte-identical — running `install` again produces exactly the same files, so
  downstream tools don't churn on unchanged content.

- `ai-harness uninstall` — removes exactly what `install` wrote, using a
  persisted manifest. Works even when the source repo is gone. No-args removes
  everything; `-o` removes only selected Agent CLIs.

- `ai-harness set-models` — interactive wizard for per-CLI model and effort
  overrides. Persists user choices to `~/.ai-harness/overrides.json` so they
  survive reinstall. Requires exactly one Agent CLI via `-o` (supports `claude`
  and `opencode`).

- `ai-harness worktree create` — creates an isolated git worktree at
  `.ai-harness/worktrees/<dir>` on a new branch, based on the current branch's
  HEAD. `-d`/`--directory-name` and `-b`/`--branch-name` set the directory and
  branch; both default to a `<Date.now()>` timestamp when omitted.
  Lazily writes a nested `.gitignore` so throwaway worktrees are never committed.
  Launch your Agent CLI inside this directory to run a change session without
  disturbing the host repo — run a grill session or a second session in parallel.
  Interactive cleanup is available via `ai-harness worktree delete`; native git
  works too: `git worktree remove .ai-harness/worktrees/<ts>` /
  `git worktree prune` / `git worktree list`.

## Getting started

Requires Python >= 3.12.

```bash
git clone https://github.com/diegoagd10/ai-harness.git
cd ai-harness
uv tool install .              # puts ai-harness on PATH (~/.local/bin/ai-harness)
# After upgrading an existing install: uv tool install --force .
ai-harness install             # copies AGENTS.md + skills into ~/.agents/
```

If you prefer not to install on PATH, use `uv run` directly:

```bash
uv run ai-harness install
```

To scaffold a consuming repository:

```bash
cd /path/to/your-project
ai-harness init
```

To remove everything the tool installed:

```bash
ai-harness uninstall
```

`ai-harness uninstall` removes only files listed in the manifest,
then removes the manifest. It does not need the source repo to be available.

## End-to-end flow

Once the Prerequisites are in place, the full workflow for turning a feature idea
into implemented code is:

```
setup-matt-pocock-skills → ai-harness init → grill-with-docs → to-prd → to-design → to-issues → change-orchestrator
```

1. **`setup-matt-pocock-skills`** — one-time skill that configures this repo for
   the engineering skills (sets up the issue tracker, triage labels, and domain
   docs). Run once per repository.

2. **`ai-harness init`** — scaffolds `CODING_STANDARDS.md` and the labels-policy
   block at the repo root. Run once per repository.

3. **`grill-with-docs`** — interview skill that stress-tests your design while
   producing ADRs and a glossary. Produces a shared understanding before writing
   code.

4. **`to-prd`** — synthesizes the grilled design into a **prd-issue** on the
   project tracker. A prd-issue holds the full product context for a unit of
   work.

5. **`to-design`** — hardens the prd-issue's light seam sketch into a rigorous
   **deep-module design**, recorded as one ADR in `docs/adr/`. That ADR is the
   seam contract: `to-issues` slices within these modules and the `change-validator`
   audits depth against it. Forward, greenfield design — the inverse of
   `improve-codebase-architecture` (which remediates existing shallow code).

6. **`to-issues`** — breaks the prd-issue into independent, grab-able
   **sub-issues** using tracer-bullet vertical slices, sliced *within* the
   modules the design ADR defined.

7. **`change-orchestrator`** — the cohesive multi-agent workflow that drives a
   file-backed *Change* through its pipeline: `change-explorer` maps the codebase
   → `change-implementor` writes the change → `change-validator` reviews it.
   Iterates implementor ↔ validator until clean, then archives.

## Running a change session in a worktree

A change session may mutate the working tree (it checks out session branches and
runs build commands). To keep your host repository undisturbed — so you can
grill, model, or run a second session in parallel — create an isolated worktree:

```bash
ai-harness worktree create
# Created worktree: .ai-harness/worktrees/1782139126824
# Created .ai-harness/.gitignore.

cd .ai-harness/worktrees/1782139126824
# Launch your Agent CLI here (Claude Code / OpenCode)
# Start the change-orchestrator session
```

Because the Agent CLI's working directory is inherited by every subagent, every
`git`, `pytest`, and file-access command operates inside the worktree by
construction — no per-command discipline needed.

When the session is done, clean up interactively or with native git:

```bash
# Interactive picker — lists worktrees, confirms, removes, prunes:
ai-harness worktree delete

# Or manual cleanup:
git worktree remove .ai-harness/worktrees/1782139126824
git worktree prune
git worktree list
```

The `delete` verb provides a convenient interactive picker; native
`git worktree remove|prune|list` remain available for scripting.

## Supported agent CLIs

`ai-harness install` copies the same persona and skills into the native
configuration directories of every supported Agent CLI:

| Agent CLI | Configuration home | Persona path |
|-----------|-------------------|--------------|
| Generic | `~/.agents/` | `~/.agents/AGENTS.md` |
| Claude Code | `~/.claude/` | `~/.claude/CLAUDE.md` |
| GitHub Copilot CLI | `~/.copilot/` | `~/.github/copilot-instructions.md` |
| OpenCode | `~/.config/opencode/` | `~/.config/opencode/AGENTS.md` |

Generic is always installed. It provides the persona for any Agent CLI
that reads from the standard `~/.agents/` directory.

## Copilot change agents

`ai-harness install` also renders the nine change agents into
`~/.copilot/agents/` as Copilot custom agent files. Each file carries a YAML
frontmatter with `name` and `description` — the fields Copilot CLI
honors for custom agents.

### Driving the change workflow

Start the change-orchestrator from within Copilot CLI:

```
/agent change-orchestrator
```

The orchestrator drives a file-backed *Change* through its pipeline and
coordinates the subagents — change-explorer (investigate), change-implementor
(apply), change-validator (review) — until the change is clean and committed.

### Subagent visibility

All change subagents are visible and directly invocable via `/agent <name>`.
They are intentionally visible so you can invoke one directly when you need
a targeted investigation or review.

### Model selection

Copilot CLI's model is a single global setting — not per-agent. Use the
Copilot-native mechanism:

- **Interactive**: `/model` in the Copilot CLI session
- **Persistent**: edit `model` in `~/.copilot/settings.json`

`ai-harness set-models` does **not** support `-o copilot`. The agent
files carry no `model` field (Copilot CLI ignores it — see
[ADR 0008](docs/adr/0008-copilot-loop-agents-native-model.md)), so the
right place to set the model is the Copilot CLI itself.

## What's in here

The project is a uv-managed Python package. The main regions of the tree:

- `src/ai_harness/` — the CLI package. The harness module owns the install/uninstall
  operations (path mapping, resource enumeration, manifest persistence); the commands
  module is a thin typer adapter over them.
- `src/ai_harness/resources/` — the bundled artifacts (`AGENTS.md`, `skills/`,
  and `change-agent/`) that the installer copies into each Agent CLI's home
  directory.
- `src/ai_harness/resources/change-agent/` — the nine change agents
  (orchestrator, explorer, implementor, validator, and support agents) that drive
  the end-to-end change workflow.
- `tests/` — Python unit tests for the CLI package. Run with `uv run pytest`.
- `e2e/` — end-to-end test suite and Docker sandbox (`e2e/docker-test.sh`).
- `docs/adr/` — architecture decision records.

The repo root also holds `pyproject.toml` (project metadata and dependencies) and
`tasks.py` (Invoke tasks for running the e2e suite).

## Running tests

Unit tests run against the Python source (no Docker needed):

```bash
uv run pytest
```

End-to-end tests run inside an isolated Docker container — no host-side effects:

```bash
./e2e/docker-test.sh                # Tier 1 only (fast, no filesystem writes)
RUN_FULL_E2E=1 ./e2e/docker-test.sh       # Tier 1 + 2 (install/uninstall lifecycle)
RUN_BACKUP_TESTS=1 ./e2e/docker-test.sh    # Tier 1 + 3 (backup/restore)
RUN_FULL_E2E=1 RUN_BACKUP_TESTS=1 ./e2e/docker-test.sh  # All tiers
```

The e2e suite is a single canonical file: `e2e/e2e_test.sh`. All behaviour
tests live in that one file; helpers are in `e2e/lib.sh`. Adding a new test
means adding a `test_*` function to `e2e/e2e_test.sh` and placing it in the
appropriate tier section.

## Commit convention

The commit-message format is owned by
[`CODING_STANDARDS.md ## Commits`](CODING_STANDARDS.md#commits) — the change agents defer
to that section instead of hardcoding a convention. The default is Conventional Commits.

Override it by editing the section. For example, to switch to a work-policy format:

```markdown
## Commits

- `[{issue_number}] <description>` — subject describes the change, issue number leads.
- One logical change per commit.
- **NEVER use the `RALPH:` prefix.**
```

## Contributing

- Run `uv run inv test` before opening a pull request.
- File issues at [https://github.com/diegoagd10/ai-harness/issues](https://github.com/diegoagd10/ai-harness/issues).
- Open pull requests against the same remote's `main` branch.
