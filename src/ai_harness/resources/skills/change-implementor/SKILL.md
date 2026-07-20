---
name: change-implementor
description: "Change implementor — drains file-backed tasks through task-next and task-done in the implement phase."
license: Apache-2.0
metadata:
  author: diegoagd10
  version: "2.0"
---

# Change Implementor

You implement tasks for one file-backed Change on the current branch,
inline in the current host, reporting to the user directly. Stay on the
current branch for the whole run; one completed task produces exactly
one commit.
After the task queue drains (or your budget runs out), you validate the
phase with the CLI and report next steps or blockers. Then you stop —
the user triggers the next phase, possibly in a fresh session, so
everything you need comes from disk and the CLI, never from
conversation memory.

## Entry

The `ai-harness` control plane gates entry: it runs `change-continue`,
requires the route to be `implement`, and loads you with the change
name, the change root, the commit-format directive, and any fresh user
context (on a fixup retry, the validator's findings). If you were
loaded without gating and the inputs below are missing or inconsistent,
run `ai-harness change-continue {change}` yourself: `nextRecommended`
must be `implement`. Anything else — another route,
`resolve-blockers`, a failed command, malformed JSON — means report
`blocked` and stop; surface `blockedReasons` verbatim in the report.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- Artifacts to read: `exploration.md`, `design.md` ONLY. Never
  `prd.md` or `specs/*.md` — task scope comes exclusively through
  `task-next`.
- `tasks.json` accessed only through `ai-harness task-*`, never a
  direct read or write.
- Commit-format directive (mandatory — see the hard gate below) and, on
  a fixup retry, the validator's findings.

## CLI contracts

This phase owns three CLI commands: `task-next` and `task-done` for the
loop, and `change-continue` for entry gating and exit validation. Their
input shapes and expected responses below are COMPLETE and
AUTHORITATIVE.

**No CLI discovery.** Never run `ai-harness --help`,
`ai-harness task-next --help`, `which ai-harness`,
`command -v ai-harness`, `ai-harness --version`, or any other discovery
command — the tool is installed and this contract is everything you
need. Go straight to the command you need with the shapes below.

### `task-next`

How it works — returns the lowest-id pending Task whose dependencies
are all done, with only its *undone* subtasks listed (already-done
subtasks are filtered out). Prints the Task JSON, or prints `null`
when nothing is pending.

Use it to — pick the next slice of work without re-reading
`tasks.json` yourself.

Expected success response — pending Task, or `null`:

```json
{
  "id": "2",
  "title": "Add CLI contracts section to change-tasks.md",
  "spec": "tasks-cli-contract",
  "phase": "core",
  "depends_on": ["1"],
  "status": "pending",
  "subtasks": [
    {"id": "2.1", "title": "Insert ## CLI contracts", "scenario": "section exists in the tasks prompt", "status": "pending"}
  ]
}
```

```json
null
```

### `task-done`

How it works — marks one task or subtask done and prints the
*containing* Task JSON. The `-i` input is a JSON object with an `"id"`
field — NOT a bare id. Pass a top-level id (`{"id": "3"}`) to mark the
whole task done; pass a dotted subtask id (`{"id": "3.2"}`) to mark
only that subtask. When the last undone subtask of a parent completes,
the parent is auto-marked done.

Use it to — close out a task or subtask after the commit lands.

Expected success response:

```json
{
  "id": "3",
  "title": "Add CLI contracts section to change-validator.md",
  "spec": "validator-cli-contract",
  "phase": "core",
  "depends_on": ["1", "2"],
  "status": "pending",
  "subtasks": [
    {"id": "3.1", "title": "Insert ## CLI contracts", "scenario": "section exists in the validator prompt", "status": "done"}
  ]
}
```

### `change-continue`

How it works — prints one ChangeStatus JSON object for the change.
You consume three fields: `artifacts` (per-phase `done`/`missing`
markers), `nextRecommended` (a phase token, or `resolve-blockers`),
and `blockedReasons`.

Use it to — gate entry on the `implement` route and validate the
phase exit after the loop drains the task queue.

Expected success response:

```json
{
  "artifacts": {"explore": "done", "prd": "done", "design": "done", "specs": "done", "tasks": "done", "implement": "done", "validate": "missing", "archive": "missing"},
  "nextRecommended": "validate",
  "blockedReasons": []
}
```

## Commit-format directive (defensive gate — CHECK FIRST)

**This gate is your step zero.** Before running `task-next`, before
reading any artifact, before writing any file: locate the
`commit-format:` directive in the invocation context (the change-flow
orchestrator injects it per delegation from the `commit_format` field of
the `configContext` object `change-continue` returned, sourced from
`.ai-harness/config.yml`'s `commit.format`). You never read
`.ai-harness/config.yml` yourself, never invent a format, and never
substitute a "reasonable default".

- **Missing directive.** If the `commit-format:` directive is absent
  (an orchestrator-level bug, not the normal flow), report
  `State: blocked` with
  `Blockers: commit-format directive missing from delegation`
  as your ONLY action — no `task-next`, no implementation, and above
  all MUST NOT attempt `git commit`. Work you cannot commit under the
  contract is work you must not start. The Blocking rule below
  applies.
- **Unknown placeholder.** After substituting `{change_name}`, `{task_id}`,
  and `{slug}` in that fixed order, scan the result with the regex
  `\{[a-z_]+\}`. Any match outside the closed set
  `{change_name, task_id, slug}` MUST trigger a `State: blocked`
  report whose `Blockers:` line carries the canonical message
  `unknown placeholder {<token>} in commit format`
  naming the offending token. MUST NOT attempt `git commit`. Rationale:
  silent substitution of garbage keeps drift invisible, which is the
  exact failure this directive exists to fix.

## Loop

0. **Directive check (hard gate).** Quote the `commit-format:` line
   from the invocation context verbatim in your first reply text,
   before any tool call. If it is absent — or an unknown placeholder
   survives substitution at commit time — stop and emit the blocked
   Report with the canonical message from the directive section above:
   no `task-next`, no file writes, no `git commit`.
1. Run:

```bash
ai-harness task-next -c {change}
```

2. If no task is returned, write or update `implementation.md`, run
   exit validation, and report `done`.
3. Implement exactly the returned task and its undone subtasks.
   TDD applies where tests exist or behavior is testable.
4. Run the task's tests plus the quality gates named in the
   forwarded `configContext.phase_rules`, scoped to the task's files.
5. Mark each completed subtask with:

```bash
ai-harness task-done -c {change} -i '{"id": "<id>"}'
```

6. Make one commit for the task. **Apply the `commit-format` directive:**
   substitute `{change_name}` with the Change name, `{task_id}` with the
   task id, and `{slug}` with a slugified form of the task title
   (lowercase, hyphens for whitespace, ASCII-only). Substitution order is
   fixed: `{change_name}` → `{task_id}` → `{slug}` (slug is generated
   last so it cannot collide with literal `{change_name}` / `{task_id}`
   segments). Pass the substituted result as the single `-m`
   argument to `git commit`, after passing the unknown-placeholder
   check from the directive section. Do not combine multiple tasks
   into one commit.
7. Append the canonical `## Commits` line, then one matching
   `## TDD Evidence` row, to
   `.ai-harness/changes/{change}/implementation.md` atomically. The
   row's `(Task, Commit)` cells match the line just written.
8. Repeat while context and time allow. If tasks remain, report
   `partial`.

## `implementation.md` structure

```markdown
# Implementation — {change}

## Commits
- <sha> — task <id>: <summary>

## TDD Evidence

| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |
|------|--------|----------------|------------|-------|------------|-----|-------|---------------|----------|
| <id> | <sha>  | <paths>        | <paths>    | unit  | passed: N/M| written | passed | Single     | clean    |

## Remaining
- <task id or none>
```

`## Commits` lines use the canonical prefix
`- <sha> — task <id>: <summary>`. A trailing `; tests: <commands>`
segment on a commit line is harmless suffix noise and is ignored by
the validator at audit time — do not strip it.

Every `## Commits` line carries exactly one matching `## TDD Evidence`
row, populated against the per-column grammar below.

`## Remaining` is the canonical on-disk record of the `partial` state
and the remaining task ids the Report block carries. Keep both aligned
so resume can recover them from disk.

## TDD evidence

The `## TDD Evidence` table is the **grammar source of truth** for
both this skill and the `change-validator` skill. The validator mirrors each
rule inline and references this skill as authority — future grammar
edits touch both files.

### Per-column value grammar

- `Task` — task id from `ai-harness task-list`.
- `Commit` — full SHA from the commit just made.
- `Non-test files` — comma-separated paths, single line, no `|`.
- `Test files` — same shape; `N/A` allowed only when `Non-test files`
  is empty (a row with non-test files and `Test files: N/A` is a
  CRITICAL behavior-without-test finding on audit).
- `Layer ∈ {unit, integration, e2e, mixed, N/A}`.
- `Safety net ∈ {(passed: N/M with 0 ≤ N ≤ M) | N/A: new files | N/A: <reason>}`.
- `RED == "written"` (literal).
- `GREEN == "passed"` (literal).
- `Triangulation ∈ {(N cases) | Single | N/A: <reason>}`.
- `Refactor ∈ {clean, none needed}`. `deferred` and any other value
  is off-grammar and a WARNING.

No `|` may appear inside any cell — pipes break Markdown table
parsing. A row that doesn't split to exactly ten cells fails the
validator's `cell-count` check as CRITICAL.

## Blocking

If you cannot proceed, stop before committing unrelated work. Leave
the working tree clean; the Report's `Blockers:` line carries the
explanation.

## Exit validation

When the loop drains the task queue and you are about to report `done`,
run `ai-harness change-continue {change}` and require BOTH:

- `artifacts.implement` is `done`, AND
- `nextRecommended` is `validate`.

Anything else — missing artifact, unchanged route, `resolve-blockers`,
a failed command, malformed JSON — is `blocked`. Surface the observed
status or CLI diagnostics verbatim in the report.

This validation applies to the `done` case only. A `partial` report
(tasks remain, orchestrator re-invokes you) and a `blocked` report do
not run it.

## Report

Emit this block, then stop:

```text
Change:    {change}
Phase:     implement
State:     done | partial | blocked
Validated: artifacts.implement=done; route advanced to validate
Commits:   <n> commits this run
Remaining: <task ids, or none>
Next:      validate — invoke change-validator
Blockers:  <diagnostics, only when blocked>
```

- `State: done` — `task-next` returns nothing; all tasks closed,
  `implementation.md` reflects every commit, and exit validation
  passed. `Next:` is `validate — invoke change-validator`.
- `State: partial` — tasks remain and `implementation.md` lists the
  remaining ids in `## Remaining` and on the `Remaining:` line. The
  orchestrator re-invokes this implementor; `Next:` is
  `implement — re-invoke change-implementor`.
- `State: blocked` — the `Blockers:` line carries the reason verbatim
  (for example `commit-format directive missing from delegation` or
  `unknown placeholder {<token>} in commit format`).
