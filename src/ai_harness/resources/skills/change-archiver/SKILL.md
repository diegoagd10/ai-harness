---
name: change-archiver
description: "Change archiver — runs ai-harness change-archive for the target Change and commits the resulting .ai-harness archive/spec movement as a single scoped docs commit."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "1.0"
---

# Change Archiver

You own the archive commit for one file-backed Change. The CLI owns the
filesystem mechanics; you own the git scoping and the user-facing
escalation. Exactly one scoped commit, scoped to archive-generated
`.ai-harness` changes only.

## Inputs

- Change name: `{change}`.
- Archive command: `ai-harness change-archive {change}`.
- `validation.md` is already on disk (the semantic gate passed before
  this phase runs). You do not re-validate semantic content.

## CLI contracts

The archiver owns one CLI command: `change-archive`. Its success token
and failure shape are local so you never probe `ai-harness --help`.

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

## Loop

1. Run exactly one archive command:

   ```bash
   ai-harness change-archive {change}
   ```

   The CLI prints `done` on success and exits zero. On failure it
   prints JSON shaped as { "errors": [...] } and exits non-zero.

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
   else is staged, abort the commit, return `status: blocked`, and
   surface the unexpected paths to the human:

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
   archive files). If anything archive-related remains, return
   `status: blocked` with the leftover paths; otherwise report
   success:

   ```bash
   git status --short
   ```

7. Report success. Your result envelope references the archive commit
   SHA and the archived artifact paths.

## Failure

When `ai-harness change-archive {change}` exits non-zero:

1. Do NOT commit. The archive move did not land, so there is nothing
   safe to commit.
2. Surface the failure to the human with the original `errors` array
   so they can decide how to proceed. Do not guess or retry blindly.

When the archive command succeeded but pre-commit verification finds
unexpected staged paths, OR post-commit verification finds leftover
archive-related paths:

1. Do NOT amend the commit. Surface the unexpected paths to the
   human with a clear summary of where verification failed.
2. Return `status: blocked` with the relevant paths in the result
   envelope so the user can decide how to proceed.

## Result

Return the **shared phase result envelope**:

```result
status:           done | blocked
artifacts:        .ai-harness/specs/{change}/, .ai-harness/archive/{change}/
summary:          <one-line summary>
semantic_facts:
  archive_commit: <sha>           (when done)
  archive_paths:  <path[, path, ...]>  (when done)
  errors:         <list[str]>     (when blocked, mirror of CLI errors array)
```

- `status: done` — archive command succeeded, pre-commit verification
  passed, the single scoped commit was created, and post-commit
  verification confirmed a clean working tree for archive-generated
  paths.
- `status: blocked` — either the archive command failed, pre-commit
  verification found unexpected staged paths, or post-commit
  verification found leftover archive-related paths. Ask the human
  for intervention. The `errors` field carries the relevant
  diagnostics so the user sees what the archiver saw.

## Constraints

- One archive commit per Change. Do not amend, re-stage, or create a
  second archive commit for the same Change.
- Unrelated product dirtiness OUTSIDE `.ai-harness/` does NOT block
  archive completion — the `git add -A .ai-harness/` scope ignores
  it. Dirtiness INSIDE `.ai-harness/` that is not archive-generated
  (sibling Change folders, experimental specs edits) IS caught by
  pre-commit verification and triggers `status: blocked`.
- You do not parse `validation.md` prose. The semantic gate is upstream
  of this phase; by the time you run, it has already decided the Change
  is semantically ready.
