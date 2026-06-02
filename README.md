# ai-harness-setup

Personal, version-controlled configuration shared across **code AI harnesses** —
Claude Code, opencode, Codex, GitHub Copilot, and any other tool that reads a
`CLAUDE.md`/`AGENTS.md` plus a skills directory.

One source of truth, symlinked into the places each harness expects.

## What's in here

| Path | Purpose |
|------|---------|
| `AGENTS.md` | The single config: persona, rules, orchestration policy, OpenSpec/SDD flow. Symlinked as both `CLAUDE.md` (Claude) and `AGENTS.md` (others). |
| `skills/` | Reusable skills (SDD apply flow, branch-pr, coding-guidelines, …). |
| `templates/openspec/config.yaml` | Starter OpenSpec project config to copy into new projects. |
| `install.sh` / `uninstall.sh` | Create / remove the home symlinks. |

## Install

```bash
git clone git@github.com:diegoagd10/ai-harness-setup.git ~/Projects/ai-harness-setup
cd ~/Projects/ai-harness-setup
./install.sh
```

`install.sh` creates these symlinks (idempotent — re-running just repoints them,
and any real file already in the way is backed up to `<path>.bak.<timestamp>`):

```
~/.claude/skills    -> <repo>/skills
~/.claude/CLAUDE.md -> <repo>/AGENTS.md
~/.agents/skills    -> <repo>/skills
~/.agents/AGENTS.md -> <repo>/AGENTS.md
```

Editing the repo edits the live config for every harness — no copy step, no drift.

## Uninstall

```bash
./uninstall.sh
```

Removes only the symlinks that point back into this repo. Real files and `*.bak.*`
backups are left untouched.

## Using the OpenSpec template in a new project

```bash
openspec init --tools claude,codex,opencode,github-copilot
cp ~/Projects/ai-harness-setup/templates/openspec/config.yaml openspec/config.yaml
```

Then customize `openspec/config.yaml` for that project.

**Important about the config:** OpenSpec only accepts `rules` for the four
spec-driven *artifacts* — `proposal`, `specs`, `design`, `tasks`. Rules under
`apply`, `verify`, or `archive` are silently ignored (they are workflow phases,
not artifacts); that guidance belongs in `AGENTS.md`. Also quote any rule that
contains `": "`, e.g. `- "Run: scripts/verify"`, or YAML parses it as a map.

After `openspec init`/`openspec update`, remove the generated `opsx-apply`
command and `openspec-apply-change` skill per tool, so they don't compete with
the custom apply flow defined in `AGENTS.md`.
