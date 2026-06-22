# Worktree bases on current branch and adds interactive delete

## Context

ADR 0007 decided that `ai-harness worktree` always creates a detached worktree
from `main`'s HEAD, and that a remove/list verb was unnecessary because native
`git worktree remove|prune|list` cover cleanup. Two friction points emerged:

1. **Hardcoded `main` base.** When the human is on a non-`main` branch (e.g.
   `master`, a feature branch) and creates a worktree, the worktree is detached
   at `main`'s HEAD — not the branch they're actively working on. The resulting
   worktree dir contains a different state than the host repo, which is confusing
   and wastes a checkout.

2. **Manual cleanup is error-prone.** Removing worktrees requires remembering
   long timestamp paths or copy-pasting from `git worktree list`. The user must
   then run `git worktree prune` separately to remove stale metadata. This is a
   three-step sequence that is easy to forget or get wrong.

## Decision

### Base on current branch

`ai-harness worktree` resolves the current branch with
`git symbolic-ref --short HEAD` and uses it as the `--detach` start-point instead
of the hardcoded `"main"`. The worktree stays detached — the orchestrator still
owns branch naming.

**Detached HEAD:** When the human checks out a detached HEAD (no current branch),
the command sets a clear warning and creates no worktree directory. There is no
fallback to `main` — the user must checkout a branch first.

The bare `ai-harness worktree` is otherwise unchanged: lazy `.gitignore` write,
"return a result with a warning, never raise" contract, same timestamp directory
naming.

### Interactive `delete` verb

`ai-harness worktree` becomes a typer sub-app: the bare command still creates
(`invoke_without_command=True`), and a new `delete` verb removes a worktree
interactively:

- Lists worktrees from `git worktree list --porcelain`, filtered to paths under
  `.ai-harness/worktrees/`. Each entry is labelled with its timestamp and
  branch name (or "detached" state).
- Shows a `questionary.select` picker with a rich `Panel` header matching the
  `set-models` wizard look. No dependency on `wizard/tui.py` private helpers.
- Asks for `questionary.confirm` (y/N) before any removal.
- Runs `git worktree remove <path>` **without `--force`** — a dirty worktree is
  refused by git and the error is surfaced, never silently destroyed.
- Runs `git worktree prune` automatically after a successful removal.
- Empty worktree list → friendly message, exit 0.
- Non-TTY → clear error (mirrors `set-models` non-TTY bail).
- Ctrl+C at any prompt → nothing removed.

All decision logic (branch resolution, listing, remove+prune) lives behind the
existing `_run` seam in `ai_harness.modules.harness.worktree`. The typer adapter
in `ai_harness.commands.worktree` only wires picker → confirm → remove.

### Architecture boundary

The interactive layer (questionary picker, rich Panel rendering, confirmation)
is intentionally left untested per the `wizard/tui.py` precedent: it is a thin
adapter over the pure decision logic which is fully tested through the `_run`
seam.

## Supersedes

This ADR supersedes two stances from ADR 0007:

- **"from `main`'s HEAD"** — the base ref is now the current branch.
- **"no remove verb"** — the `delete` verb now provides interactive cleanup.

## Consequences

- The `_run` seam in `create_worktree` now sees two calls: `git symbolic-ref`
  then `git worktree add`. Fake runners in tests must handle this (the
  `_MultiFakeRun` helper covers it).
- `CONTEXT.md` and `README.md` worktree sections are updated to reflect the
  current-branch base and the `delete` verb.
- The CLI adapter no longer prints "Created worktree" when the worktree was not
  actually created (warning path).
- `invoke_without_command=True` on the worktree sub-app preserves backward
  compatibility: bare `ai-harness worktree` still creates.
