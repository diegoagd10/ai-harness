# ai-harness-setup

Personal, version-controlled configuration for the **OpenCode** code-AI harness:
one source of truth (`AGENTS.md` + a skills directory + SDD prompts), generated
into the places OpenCode expects.

> **Scope:** today this repo targets **OpenCode** only. Once the OpenCode setup is
> solid it becomes the reference for other harnesses (Claude Code, Copilot).

## What's in here

| Path | Purpose |
|------|---------|
| `AGENTS.md` | The single config: persona, rules, orchestration policy, OpenSpec/SDD flow. |
| `prompts/sdd/` | Platform-neutral SDD phase prompts (the executor prompts the orchestrator drives). |
| `prompts/commands/` | Platform-neutral slash-command entrypoints, the single source of truth. |
| `skills/` | Reusable skills (SDD apply flow, branch-pr, coding-guidelines, …). |
| `agent-clis/opencode/` | The OpenCode wiring: agent graph (`opencode.json`), orchestrator prompt, blocks, plugins. |
| `cli/` | The `ai-harness` Go CLI: SDD dispatcher + installer that generates the OpenCode slash-commands. |
| `templates/openspec/config.yaml` | Starter OpenSpec project config to copy into new projects. |

## Install

Build the CLI and generate the OpenCode integration:

```bash
git clone git@github.com:diegoagd10/ai-harness-setup.git ~/Projects/ai-harness-setup
cd ~/Projects/ai-harness-setup/cli
make install            # put the `ai-harness` binary on your PATH
ai-harness install      # generate the OpenCode slash-commands into ~/.config/opencode/commands/
```

`ai-harness install` reads the canonical `prompts/commands/*.md` and writes the
OpenCode-specific command files under `~/.config/opencode/`. Editing the repo
edits the source those files are generated from — re-run `ai-harness install` to
regenerate. See `agent-clis/opencode/README.md` for how the agent graph fits
together.

## Uninstall

```bash
ai-harness uninstall
```

Removes only the OpenCode command files this repo generated.

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
