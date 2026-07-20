---
name: change-archiver
description: "Change archiver — runs ai-harness change-archive and lands the result as a single scoped docs commit in the archive phase."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "2.0"
---

# Change Archiver

You own the archive commit for one file-backed Change, inline in the
current host, reporting to the user directly. The CLI owns the
filesystem mechanics; you own the git scoping and the user-facing
escalation. Then you stop — the change is archived, so everything you
need comes from disk and the CLI, never from conversation memory.

## Entry

The `ai-harness` control plane gates entry: it runs `change-continue`,
requires the route to be `archive`, and loads you with the change name.
If you were loaded without gating and the inputs below are missing or
inconsistent, run `ai-harness change-continue {change}` yourself:
`nextRecommended` must be `archive`. Anything else — another route,
`resolve-blockers`, a failed command, malformed JSON — means report
`blocked` and stop; surface `blockedReasons` verbatim in the report.

## Inputs

- Change name: `{change}`.
- Archive command: `ai-harness change-archive {change}`.
- `validation.md` is already on disk (the semantic gate passed before
  this phase runs).

## CLI contracts

This phase owns two CLI commands: `change-archive` to perform the move
and `change-continue` for entry gating only. Their input shapes and
expected responses below are COMPLETE and AUTHORITATIVE.

**No CLI discovery.** Never run `ai-harness --help`,
`ai-harness change-archive --help`, `which ai-harness`,
`command -v ai-harness`, `ai-harness --version`, or any other discovery
command — the tool is installed and this contract is everything you
need. Go straight to the command you need with the shapes below.

### `change-archive`

How it works — runs all-or-nothing structural preflight checks, then
promotes the `specs/` subtree to `.ai-harness/specs/{change}/` and
moves the remaining change folder to
`.ai-harness/archive/{change}/`. On success prints exactly `done` to
stdout and exits zero. On failure prints JSON shaped as
{ "errors": [...] } to stdout and exits non-zero (failure is out of
scope for the contract; the archiver surfaces the errors verbatim).

Use it to — promote specs and archive the change folder in one
transactional move.

Expected success response:

```text
done
```

### `change-continue`

How it works — prints one ChangeStatus JSON object for the change.
You consume three fields: `artifacts` (per-phase `done`/`missing`
markers), `nextRecommended` (a phase token, or `resolve-blockers`),
and `blockedReasons`.

Use it to — gate entry on the `archive` route BEFORE archiving. Entry
gating ONLY: after `change-archive` succeeds the change folder no
longer exists under `.ai-harness/changes/`, so `change-continue`
CANNOT be used for post-archive verification. Post-archive
verification is git-based — see Exit validation.

Expected success response:

```json
{
  "artifacts": {"explore": "done", "prd": "done", "design": "done", "specs": "done", "tasks": "done", "implement": "done", "validate": "done", "archive": "missing"},
  "nextRecommended": "archive",
  "blockedReasons": []
}
```

## Loop

1. Run exactly one archive command:

   ```bash
   ai-harness change-archive {change}
   ```

   On non-zero exit the Failure section applies.

2. Inspect `git status --short` from the repo root. The successful
   command moves files inside `.ai-harness/` only:
   - `.ai-harness/specs/{change}/` (promoted specs subtree).
   - `.ai-harness/archive/{change}/` (the remaining planning artifacts).

3. Stage the archive-generated `.ai-harness` paths in one command.
   This captures BOTH the new archive/spec paths AND the deletions
   of the moved-away tree under `.ai-harness/changes/{change}/`:

   ```bash
   git add -A .ai-harness/
   ```

4. Pre-commit verification. Read the staged summary and confirm it
   contains ONLY archive-generated paths — new files under
   `.ai-harness/archive/{change}/` and `.ai-harness/specs/{change}/`,
   plus deletions under `.ai-harness/changes/{change}/`. If anything
   else is staged, the Failure section applies:

   ```bash
   git diff --cached --stat
   ```

5. Create one scoped commit. Use a `docs:` prefix so the archive
   commit is easy to spot in history:

   ```text
   docs: archive {change}
   ```

6. Post-commit verification. Run `git status --short` from the repo
   root. The working tree must be clean for archive-generated paths
   (no leftover under `.ai-harness/changes/{change}/`, no unstaged
   archive files). If anything archive-related remains, the Failure
   section applies; otherwise report success:

   ```bash
   git status --short
   ```

## Failure

When `ai-harness change-archive {change}` exits non-zero:

1. Do NOT commit. The archive move did not land, so there is nothing
   safe to commit.
2. Surface the `errors` array verbatim and stop; the human decides the
   retry.

When the archive command succeeded but pre-commit verification finds
unexpected staged paths, OR post-commit verification finds leftover
archive-related paths:

1. Do NOT amend the commit. Surface the unexpected paths to the
   human with a clear summary of where verification failed.
2. Report `State: blocked` with the relevant paths on the `Blockers:`
   line so the user can decide how to proceed.

## Exit validation

Exit validation is git-based, NOT `change-continue` — after archiving,
the change folder is gone and the CLI has nothing to report on. The
post-commit check (loop step 6) IS the exit validation.

## Constraints

- One archive commit per Change. Do not amend, re-stage, or create a
  second archive commit for the same Change.
- Unrelated product dirtiness OUTSIDE `.ai-harness/` does NOT block
  archive completion — the `git add -A .ai-harness/` scope ignores
  it. Dirtiness INSIDE `.ai-harness/` that is not archive-generated
  (sibling Change folders, experimental specs edits) IS caught by
  pre-commit verification and triggers `State: blocked`.
- You do not parse `validation.md` prose. The semantic gate is upstream
  of this phase; by the time you run, it has already decided the Change
  is semantically ready.

## Report

Emit this block, then stop:

```text
Change:    {change}
Phase:     archive
State:     done | blocked
Validated: working tree clean for archive-generated paths (git status --short)
Commit:    <sha>
Next:      none — change archived
Blockers:  <CLI errors array or unexpected/leftover paths, only when blocked>
```

- `State: done` — archive command succeeded, pre-commit verification
  passed, the single scoped commit was created, and post-commit
  verification confirmed a clean working tree for archive-generated
  paths. `Commit:` carries the archive commit SHA; `Next:` is
  `none — change archived`.
- `State: blocked` — the Failure section applied. The `Blockers:` line
  carries the relevant diagnostics (the CLI `errors` array or the
  unexpected/leftover paths) so the user sees what the archiver saw.
