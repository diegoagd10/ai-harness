# Spec — apply-injected-commit-format

## Purpose

The implementor-side applier that consumes the `commit-format:` directive
inlined by the orchestrator at delegation-build time. Lives in
`change-implementor.md` loop step 6. Reads the injected format string
verbatim, substitutes `{change_name}` with the Change name,
`{task_id}` with the task id, and `{slug}` with a slugified form of the
task title, and passes the result as the single `-m` argument to
`git commit`. The format string is the contract surface; the implementor
honors whatever the orchestrator injected (or fails loud).

**Option B seam.** This capability is the apply side of the
orchestrator-injects pattern. The orchestrator owns the read
(`resolve_commit_format`); the implementor owns the substitution. The
two layers meet on the literal format string, with the three tokens
documented as a stable contract (PRD §Goals G2).

**Slug stays in the implementor.** `{slug}` generation continues to live
in the implementor's task-title processing (PRD G4). The injected format
is the contract for the rest of the message; the slug rule is
implementor-internal.

## Requirements

### Requirement: implementor uses the injected format at loop step 6
The implementor MUST locate the `commit-format:` directive in the
delegation block above. The implementor MUST substitute `{change_name}`
with the Change name, `{task_id}` with the task id, and `{slug}` with a
slugified form of the task title (lowercase, hyphens for whitespace,
ASCII-only). The implementor MUST pass the substituted result as the
single `-m` argument to `git commit`.

#### Scenario: implementor commits with substituted tokens
GIVEN the implementor receives a delegation block with
`commit-format: [{change_name}][{task_id}] {slug}`
AND the Change is `implementor-reads-commit-format`
AND the task id is `T1`
AND the task title is `Resolve commit format from standards`
WHEN the implementor executes loop step 6
THEN the implementor MUST substitute `{change_name}` →
`implementor-reads-commit-format`
AND `{task_id}` → `T1`
AND `{slug}` → `resolve-commit-format-from-standards`
AND MUST pass the result
`[implementor-reads-commit-format][T1] resolve-commit-format-from-standards`
as the single `-m` argument to `git commit`.

### Requirement: substitution order is fixed
The implementor MUST substitute tokens in the order `{change_name}` →
`{task_id}` → `{slug}`. The order matters because `{slug}` is generated
last and must not collide with literal `{change_name}` / `{task_id}`
segments already in the format string.

#### Scenario: slug substitution cannot corrupt earlier tokens
GIVEN the format string `[{change_name}][{task_id}] {slug}`
AND the implementor-generated slug is
`implementor-reads-commit-format-resolve-commit-format-from-standards`
(contains the literal substring `implementor-reads-commit-format`)
WHEN the implementor substitutes tokens
THEN `{slug}` MUST be substituted last
AND the earlier substitutions of `{change_name}` and `{task_id}` MUST
NOT be re-substituted against the slug value
AND the final committed message MUST contain the literal `change_name`
and `task_id` tokens exactly once each.

### Requirement: format change propagates without code edits
A change to the `## Commits` body line in `CODING_STANDARDS.md` MUST
propagate to every subsequent per-task commit without editing any agent
prompt file. The orchestrator MUST re-read the standards file per
delegation so a mid-session edit takes effect on the next task.

#### Scenario: owner edits CODING_STANDARDS.md ## Commits body
GIVEN the repo owner changes the `## Commits` body to
`` `feat({change_name}): {slug} [{task_id}]` ``
AND no agent prompt file is edited
WHEN a Change task completes
THEN `git log -1 --format=%s` MUST equal
`feat(<change>): <slug> [<task-id>]`
AND no prompt edit MUST have been required.

### Requirement: commit subject retains all three tokens
For any well-formed format containing `{change_name}`, `{task_id}`, and
`{slug}`, the implementor's commit subject MUST contain all three
substituted tokens and MUST NOT contain literal placeholders.

#### Scenario: any well-formed format produces all three tokens
GIVEN any well-formed format containing the three documented tokens
WHEN the implementor commits
THEN the commit subject MUST contain all three substituted tokens
AND MUST NOT contain literal placeholders such as `{change_name}`,
`{task_id}`, or `{slug}`.