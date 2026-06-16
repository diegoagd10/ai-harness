# ai-harness-setup

Personal, version-controlled configuration for AI coding harnesses: one source
of truth (`AGENTS.md` + skills + SDD prompts), copied into the places OpenCode,
Claude Code, Copilot, and generic `.agents` consumers expect.

## What's in here

| Path | Purpose |
|------|---------|
| `AGENTS.md` | The single config: persona, rules, orchestration policy, OpenSpec/SDD flow. |
| `prompts/sdd/` | Platform-neutral SDD phase prompts (the executor prompts the orchestrator drives). |
| `prompts/commands/` | Platform-neutral slash-command entrypoints, the single source of truth. |
| `skills/` | Reusable skills (SDD apply flow, branch-pr, coding-guidelines, …). |
| `agent-clis/opencode/` | The OpenCode wiring: agent graph (`opencode.json`), orchestrator prompt, blocks, plugins. |
| `cli/` | The `ai-harness` Python CLI (uv + Typer + Rich). See [CLI](#cli). |
| `templates/openspec/config.yaml` | Starter OpenSpec project config to copy into new projects. |

## CLI

`cli/` is a [uv](https://docs.astral.sh/uv/)-managed Python package built with
[Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/),
providing the `ai-harness` command.

```bash
cd cli
uv run ai-harness install
```

### Installing the `ai-harness` binary

```bash
cd cli
uv tool install .              # install on PATH (~/.local/bin/ai-harness)
uv tool install --reinstall .  # update after pulling code changes
uv tool uninstall cli           # remove
```

End-to-end tests live in `e2e/` and run the installed `ai-harness` binary
(not `uv run`) inside Docker or locally with isolated sandboxes:

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

## Install

Build the CLI and install the harness artifacts:

```bash
git clone git@github.com:diegoagd10/ai-harness-setup.git ~/Projects/ai-harness-setup
cd ~/Projects/ai-harness-setup/cli
make install            # put the `ai-harness` binary on your PATH
ai-harness install      # copy skills/config and generate OpenCode commands/config
```

`ai-harness install` copies the shared skills/config into harness home dirs
(`~/.agents`, `~/.claude`, `~/.copilot`, and `~/.config/opencode` by default),
generates OpenCode slash-command files from `prompts/commands/*.md`, writes the
OpenCode config, and records owned files in
`~/.config/ai-harness/install-manifest.json`. Editing the repo edits the source
for those copied/generated files — re-run `ai-harness install` to refresh them.
See `agent-clis/opencode/README.md` for how the OpenCode agent graph fits
together.

## Uninstall

```bash
ai-harness uninstall
```

Removes only files listed in the central ai-harness manifest, then removes the
manifest. It does not need the source repo to be available.

## Using the OpenSpec template in a new project

```bash
openspec init --tools opencode
cp ~/Projects/ai-harness-setup/templates/openspec/config.yaml openspec/config.yaml
```

Then customize `openspec/config.yaml` for that project.

**Important about the config:** OpenSpec only accepts `rules` for the four
spec-driven *artifacts* — `proposal`, `specs`, `design`, `tasks`. Rules under
`apply`, `verify`, or `archive` are silently ignored (they are workflow phases,
not artifacts); that guidance belongs in `AGENTS.md`. Also quote any rule that
contains `": "`, e.g. `- "Run: scripts/verify"`, or YAML parses it as a map.

After `openspec init`/`openspec update`, remove the generated `opsx-apply`
command and `openspec-apply-change` skill, so they don't compete with the custom
apply flow defined in `AGENTS.md`.
