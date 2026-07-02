> **Superseded** — the loop agent set was removed in the `deprecate-loop` change.
> This ADR is retained as a historical decision record.

# Run the loop in a git worktree, launched by the human

## Context

The loop-orchestrator drives the loop by checking out branches (`loop-run/<ts>`
and per-issue sub-branches) in the repository it runs in. That mutates the
single working tree, so a human cannot run a `grill-with-docs` / domain-modeling
session (which edits `CONTEXT.md`, ADRs) in the same repo at the same time — the
loop's checkouts swap files out from under them, and their edits look like
uncommitted changes to the loop. Running two loops at once collides the same
way.

## Decision

Isolation is a separate git **worktree**, and the **human** puts the loop in it
— not the orchestrator. A new CLI command:

```
ai-harness worktree
```

runs `git worktree add --detach <repo>/.ai-harness/worktrees/<Date.now()> main`
and, lazily on first run, writes `.ai-harness/.gitignore` containing
`worktrees/`. The user then launches their agent CLI (Claude Code / OpenCode)
with its cwd set to that worktree dir and starts the loop there.

Because cwd is inherited by every subagent, every `pytest`, and every `git`
call, isolation holds **by construction** — there is no per-command rule for the
model to forget. The host repo stays untouched, so grilling proceeds in
parallel. Each invocation makes a fresh `<ts>` dir on its own detached HEAD, so
parallel loops / loop + grill just work.

The command is deliberately dumb plumbing: it does not create the `loop-run`
branch (the orchestrator still owns branch naming) and has no remove/list verb
(`git worktree remove|prune|list` already cover cleanup; documented in README).

## Considered options

- **Pass the worktree path to every subagent and instruct "work under it".**
  Rejected: relies on the model targeting the path on *every* git, test, and
  file command; one miss silently operates on the host tree. Physical cwd is
  deterministic, prompt discipline is not.
- **Orchestrator creates and manages the worktree itself.** Rejected: it would
  have to remove its own cwd at session end, and it duplicates the
  `loop/run/active` resume logic. Keeping the worktree human-launched keeps the
  orchestrator prompt almost unchanged.

## Consequences

- Two lines change in `loop-orchestrator.md`: the boot assumption (host on `main`
  *or* a detached worktree at `main`'s HEAD) and session setup, which must
  **never `git checkout main`** (it fails when `main` is already checked out in
  the host worktree). It uses `git checkout -b loop-run/<ts> origin/main` (or
  `main` with no remote) — main as a start-point ref, never as HEAD. A future
  reader must not "simplify" this back to `git checkout main`.
- Resume across a *different* worktree dir is out of scope: the
  `loop/run/active` resume assumes the same dir. Re-launching the same loop-run
  branch in a new worktree would hit git's "already checked out" guard. Not
  handled until it's actually needed.
