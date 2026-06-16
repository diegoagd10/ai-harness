# Proposal: Improve README onboarding

## Why

An engineer evaluating ai-harness-setup today lands on a README that points at a `cli/` directory that no longer exists, recommends `make install` (no Makefile in the worktree), and references `prompts/commands/*.md` (no such source in the bundled resources). The copy-paste install path is broken. There is no problem statement and no contributor entry point — just a flat file inventory. They bounce.

This rewrite gives evaluators the problem first, then the install in three commands that actually work (`git clone`, `uv tool install .`, `ai-harness install`), the SDD workflow the tool enables, and a clear contributor entry point. It addresses the engineer evaluating the tool, not the project author maintaining internal notes.

## What changes

- **Rewrite `README.md`** at worktree root. New section order:
  1. `# ai-harness-setup` — one-line tagline.
  2. `## Why we built this` — pain of generic LLM output and fix-it cycles.
  3. `## What this tool does` — SDD planning-first workflow.
  4. `## Getting started` — `git clone`, `uv tool install .`, `ai-harness install` (Python >=3.12). Mention `uv run ai-harness install` as no-install alternative. End with `ai-harness uninstall` one-liner.
  5. `## Using the OpenSpec template in a new project` — kept from current README, placed after install as the logical next step.
  6. `## What's in here` — directory table mapping paths to purposes.
  7. `## Running tests` — `uv run inv test`, per-category tasks, `e2e/docker-test.sh`.
  8. `## Contributing` — tests, issues, PRs against `git@github.com:diegoagd10/ai-harness-setup.git`.
  9. `## See also` — omitted; the only sub-README is being deleted and no other references remain.

- **Replace broken sections.** Current `## CLI`, `## Install`, `## Uninstall` removed. Functional content merged into `## Getting started` (install/uninstall) and `## Running tests` (test commands).

- **Delete `src/ai_harness/resources/agent-clis/opencode/README.md`.** Safe: `main.py` lines 17–18 source only `opencode.json` from that directory; neither `install` nor `uninstall` touch the README.

- **Migrate non-trivial content** from the deleted sub-README into the new root README:
  - **SDD-pipeline ASCII diagram** → `## What this tool does`, as visual explanation of the planning-first workflow.
  - **`{{HOME}}` placeholder explanation** → `## What's in here`, under the `agent-clis/opencode/` row in the directory table.

- **No source code changes.** No changes to other files, skill definitions, or CLI install/uninstall behavior.

## Impact

| Area | Impact | Description |
|------|--------|-------------|
| `README.md` | Modified | Full rewrite to new section structure |
| `src/ai_harness/resources/agent-clis/opencode/README.md` | Deleted | Content migrated to root README |

- **Users affected:** anyone cloning the repo and reading the README gets a working install path and problem context. `ai-harness install` users are unaffected — confirmed by `main.py`: only `opencode.json` is sourced from `agent-clis/opencode/`, not the README (lines 17–18).
- **Coordination risk with `refactor-commands-install-uninstall`:** that branch builds an `ArtifactManifest` enumerating resource files. If it lists `agent-clis/opencode/README.md`, a merge conflict arises. **Mitigation:** confirm the refactor manifest does not enumerate documentation files (it should only list files the CLI copies — `opencode.json`, not READMEs). If it mistakenly includes README files, defer deletion to a follow-up after that branch merges.

## Out of scope

- Changing any sub-README besides the one being deleted (there are no others).
- Adding `.github/`, issue templates, or PR templates.
- Rewriting the SDD pipeline implementation or install/uninstall code.
- Adding "See also" links to non-existent documents.
- Translating the README to Spanish (bundled `AGENTS.md` requires English for artifacts).

## Acceptance criteria

1. `README.md` contains all of these as top-level headings: `## Why we built this`, `## What this tool does`, `## Getting started`, `## Running tests`, `## Contributing` (`grep '^## ' README.md | wc -l` >= 5).
2. `README.md` contains `uv tool install .` and does NOT contain `cd cli`, `make install`, or `prompts/commands/` (verify with `grep -c 'cd cli' README.md` returns 0, same for `make install` and `prompts/commands/`).
3. `README.md` contains the heading `## Using the OpenSpec template in a new project` and the command `openspec init --tools opencode`.
4. `src/ai_harness/resources/agent-clis/opencode/README.md` does not exist (`test ! -f src/ai_harness/resources/agent-clis/opencode/README.md`).
5. The SDD-pipeline ASCII diagram from the deleted sub-README is preserved verbatim in `README.md` (verify both `sdd-orchestrator (primary)` and `sdd-init → sdd-explore → sdd-propose` appear in the file).

## Open questions

None.
