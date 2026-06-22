# Base worktrees on the current branch and add a `delete` verb

> [!NOTE]
> The "bare callback unchanged" stance in this ADR (lines 36–39, 69) is
> superseded by [0009](./0009-worktree-create-subcommand.md): the bare form
> (`ai-harness worktree`) is now `ai-harness worktree create`. The rest of this
> ADR (current-branch base, `delete` verb) still stands unchanged.

Supersedes the relevant parts of
[0007](./0007-loop-worktree-isolation.md): the base ref ("from `main`") and the
"no remove/list verb" stance. The rest of 0007 (human-launched isolation, cwd
holds by construction, orchestrator owns branch naming) still stands.

## Context

0007 introduced `ai-harness worktree`, which ran
`git worktree add --detach <repo>/.ai-harness/worktrees/<ts> main` and
deliberately shipped **no** cleanup verb, deferring to native
`git worktree remove|prune|list`.

Two things hurt in practice:

- **Hardcoded `main`.** A human running the command from a different base branch
  (e.g. `master`, or a release branch) got a worktree off `main`'s HEAD, not the
  branch they were actually on — surprising and wrong for their context.
- **Manual cleanup is error-prone.** Removing a throwaway worktree means copying
  the right `<ts>` path into `git worktree remove`, then remembering to run
  `git worktree prune`. The path is an opaque `Date.now()` timestamp, so picking
  the correct one by hand is exactly the step that goes wrong, and the `prune`
  is easy to forget.

## Decision

**Base on the current branch.** `ai-harness worktree` resolves the current
branch with `git symbolic-ref --short HEAD` and uses it as the `--detach`
start-point instead of the literal `main`. When HEAD is detached (no current
branch), the command **fails with a clear error and creates nothing** — there is
no implicit fallback to `main`. The worktree stays detached; the orchestrator
still owns branch naming.

**Add `ai-harness worktree delete`.** `worktree` becomes a typer sub-app:

```
ai-harness worktree          # creates (unchanged — invoke_without_command)
ai-harness worktree delete   # interactive removal
```

`delete` lists the worktrees registered under `.ai-harness/worktrees/`
(`git worktree list --porcelain`, filtered to that path) in a `questionary`
picker styled to match the `set-models` wizard (rich `Panel` header + legend).
After a `questionary.confirm`, it runs `git worktree remove <path>` **without
`--force`** — a dirty worktree is refused and git's own error is surfaced, never
silently destroyed — then `git worktree prune` to clear stale metadata. No
matching worktrees → a friendly message and exit 0.

## Considered options

- **Keep `main` hardcoded.** Rejected: the human's working branch is the right
  default; `main` was an accident of the first implementation.
- **Fall back to `main` on detached HEAD.** Rejected: silently basing off a
  different branch than the user expects is the bug we're fixing. Fail loudly.
- **No cleanup verb, rely on native git (0007's stance).** Rejected: the opaque
  timestamp paths make manual `remove` the error-prone step, and `prune` is
  forgotten. A picker removes both failure modes.
- **`--force` by default (or always).** Rejected: it would silently destroy
  uncommitted work in a worktree. Refuse-and-report keeps the safety git already
  provides.
- **Add a `rich` dependency for the picker / extract shared TUI helpers.**
  Rejected: `rich` is already available and `questionary` already a dependency;
  a plain `questionary.select` plus a rich header matches the look without
  coupling the worktree command to the `set-models` wizard's private helpers.

## Consequences

- `ai-harness worktree` (bare) behaves identically to 0007 except for the base
  ref, so existing docs and muscle memory keep working.
- `prune` runs globally, but it only clears admin metadata for worktrees whose
  directory is already gone — it never deletes a live worktree, so scoping the
  destructive step to the selected path (`remove <path>`) is sufficient.
- README and `CONTEXT.md` references to "detached at `main`'s HEAD" and
  "cleanup via native git only" are updated to match.
