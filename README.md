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
`to-prd`, `to-issues`, and the loop agents). Install them once per machine with
the `skills` CLI:

```bash
pnpm dlx skills install
```

This reads `skills-lock.json` and installs for both Claude Code and the generic
agents home (`~/.agents/skills/`). OpenCode reads skills from the generic agents
home, so one install covers both.

## What this tool does

**ai-harness** is a persona, skills, and loop-agent installer for AI coding
Agent CLIs. It copies a bundled `AGENTS.md` (the persona) and a `skills/`
directory into each supported Agent CLI's native config directory, and renders
the loop agents (`loop-agent/`) for CLIs with native agent support (Claude Code
and OpenCode). You manage one set of files; the tool distributes them everywhere
they need to go.

Five commands:

- `ai-harness init` — **repo-local** scaffolding. Run inside a consuming
  repository to create the artifacts the loop and skill flow assume at the repo
  root: a `CODING_STANDARDS.md` skeleton, a labels-policy block in the repo's
  agent doc, and the loop's GitHub labels. Idempotent — never clobbers
  human-edited content. Distinct from `install`, which distributes the harness
  globally into each Agent CLI's `$HOME` config.

- `ai-harness install` — **global** distribution. Copies `AGENTS.md` + skills
  into each Agent CLI's config dir, and renders the loop agents into the native
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
  `.ai-harness/worktrees/<Date.now()>`, detached at the current branch's HEAD.
  Lazily writes a nested `.gitignore` so throwaway worktrees are never committed.
  Launch your Agent CLI inside this directory to run the loop without disturbing
  the host repo — run a grill session or a second loop in parallel. Interactive
  cleanup is available via `ai-harness worktree delete`; native git works too:
  `git worktree remove .ai-harness/worktrees/<ts>` / `git worktree prune` /
  `git worktree list`.

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

To scaffold a consuming repository for the loop workflow:

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
setup-matt-pocock-skills → ai-harness init → grill-with-docs → to-prd → to-design → to-issues → loop
```

1. **`setup-matt-pocock-skills`** — one-time skill that configures this repo for
   the engineering skills (sets up the issue tracker, triage labels, and domain
   docs). Run once per repository.

2. **`ai-harness init`** — scaffolds `CODING_STANDARDS.md`, the labels-policy
   block, and GitHub labels at the repo root. Run once per repository.

3. **`grill-with-docs`** — interview skill that stress-tests your design while
   producing ADRs and a glossary. Produces a shared understanding before writing
   code.

4. **`to-prd`** — synthesizes the grilled design into a **prd-issue** on the
   project tracker. A prd-issue holds the full product context for a unit of
   work.

5. **`to-design`** — hardens the prd-issue's light seam sketch into a rigorous
   **deep-module design**, recorded as one ADR in `docs/adr/`. That ADR is the
   seam contract: `to-issues` slices within these modules and the loop's
   `validator` audits depth against it. Forward, greenfield design — the inverse
   of `improve-codebase-architecture` (which remediates existing shallow code).

6. **`to-issues`** — breaks the prd-issue into independent, grab-able
   **sub-issues** using tracer-bullet vertical slices, sliced *within* the
   modules the design ADR defined. Each sub-issue is labeled for the loop to
   pick up.

7. **Loop** — the cohesive multi-agent workflow that drains ready sub-issues onto
   session branches: `explorer` reads the issue and maps the codebase →
   `implementor` writes the change → `validator` reviews it. The loop iterates
   implementor ↔ validator until clean, then commits.

## Running the loop in a worktree

The loop mutates the working tree (it checks out session branches and runs build
commands). To keep your host repository undisturbed — so you can grill, model, or
run a second loop in parallel — create an isolated worktree:

```bash
ai-harness worktree create
# Created worktree: .ai-harness/worktrees/1782139126824
# Created .ai-harness/.gitignore.

cd .ai-harness/worktrees/1782139126824
# Launch your Agent CLI here (Claude Code / OpenCode)
# Start the loop: "drain the backlog" / "start the loop"
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

The command is deliberately thin plumbing: it does not create the `loop-run`
branch (the orchestrator still owns branch naming).  The `delete` verb provides
a convenient interactive picker; native `git worktree remove|prune|list` remain
available for scripting.

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

## Copilot loop agents

`ai-harness install` also renders the four loop agents into
`~/.copilot/agents/` as Copilot custom agent files
(`loop-orchestrator.agent.md`, `explorer.agent.md`,
`implementor.agent.md`, `validator.agent.md`). Each file carries a YAML
frontmatter with `name` and `description` — the fields Copilot CLI
honors for custom agents.

### Driving the Loop

Start the Loop from within Copilot CLI:

```
/agent loop-orchestrator
```

The orchestrator picks up ready sub-issues from the project tracker and
coordinates the three subagents — explorer (investigate), implementor
(apply), validator (review) — until the change is clean and committed.

### Subagent visibility

All three subagents are visible and directly invocable:

| Agent | Purpose | Invocation |
|-------|---------|------------|
| **explorer** | Read-only codebase investigation plan | `/agent explorer` |
| **implementor** | Applies the implementor workflow to one change | `/agent implementor` |
| **validator** | Read-only diff audit after implementation | `/agent validator` |

The subagents are intentionally visible so you can invoke one directly
when you need a targeted investigation or review without running the
full Loop.

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
- `src/ai_harness/resources/` — the bundled artifacts (`AGENTS.md`, `skills/`, and
  `loop-agent/`) that the installer copies into each Agent CLI's home directory.
- `src/ai_harness/resources/loop-agent/` — the four loop agents (orchestrator,
  explorer, implementor, validator) that drive the end-to-end workflow.
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

## Commit convention

The commit-message format is owned by
[`CODING_STANDARDS.md ## Commits`](CODING_STANDARDS.md#commits) — the loop's agents defer
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
