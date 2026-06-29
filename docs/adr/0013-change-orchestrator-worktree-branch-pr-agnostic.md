# change-orchestrator is worktree/branch/PR-agnostic; no `main` guard

`loop-orchestrator` must run inside a dedicated worktree on a non-`main` branch
and **refuses to run on `main`**, because it autonomously drains a backlog and an
accidental commit (or a bad PR) straight to `main` would be costly. By contrast
`change-orchestrator` is **human-driven and interactive** — the human decides how
much isolation a given change deserves.

We decided that `change-orchestrator` is **location-agnostic**: it runs wherever
it is launched — a worktree, a feature branch, or even `main` — with **no branch
guard**. It commits to whatever branch is current, creates **no** branches or
worktrees, and opens **no** PR. "One change = one PR" is a recommended human
convention, not enforced by the agent. Landing (push + PR) is **out-of-band** —
the human or the `branch-pr` skill. This is a deliberate deviation from
loop-orchestrator's hard `main` guard.

## Consequences

- A reader comparing the two orchestrators will see the inconsistency (one
  forbids `main`, one allows it). It is **intentional** — recorded here so nobody
  "fixes" change-orchestrator by adding the loop's guard.
- Running a change on `main` commits the planning artifacts under
  `.ai-harness/changes/` (which is tracked — only `worktrees/` is gitignored) and
  the change's code directly to `main`. That is the human's explicit choice; the
  agent does not prevent it.
- Because nothing pushes or opens a PR automatically, a change can complete
  (through `archive`) without ever reaching a remote — the trail and promoted
  specs live in the working tree until a human lands them.
