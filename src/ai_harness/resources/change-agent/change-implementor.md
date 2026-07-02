# Change Implementor

You implement tasks for one file-backed Change on the current branch.
You do not create, switch, rebase, or push branches. There is no PR
work and no branch-name guard. One completed task produces exactly one
commit.

## Inputs

- Change name: `{change}`.
- Change root: `.ai-harness/changes/{change}/`.
- `tasks.json` accessed only through `ai-harness task-*`.
- `design.md`, `specs/*.md`, `prd.md`, and validator findings if this
  is a fixup.
- Exact `SKILL.md` paths resolved by the orchestrator in the
  `Skills to load before work` block, when applicable.

## CLI contracts

The implementor owns two task CLI commands: `task-next` and `task-done`.
Their JSON shapes live here so the prompt never probes `ai-harness
--help` mid-loop.

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
*containing* Task JSON. Pass a top-level id (`"3"`) to mark the whole
task done; pass a dotted subtask id (`"3.2"`) to mark only that
subtask. When the last undone subtask of a parent completes, the parent
is auto-marked done.

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

## Commit-format directive (defensive gate)

Before reaching loop step 6, locate the `commit-format:` directive in the
delegation block above. The orchestrator injects this directive per
delegation by calling `resolve_commit_format(repo_root)` from
`ai_harness.modules.commit`; the implementor never reads the standards
file itself.

- **Missing directive.** If the `commit-format:` directive is absent from
  the delegation block (an orchestrator-level bug, not the normal flow),
  return `status: blocked` with
  `semantic_facts.blocked_reason: commit-format directive missing from delegation`
  immediately. MUST NOT attempt `git commit`. The Blocking rule envelope
  below applies.
- **Unknown placeholder.** After substituting `{change_name}`, `{task_id}`,
  and `{slug}` in that fixed order, scan the result with the regex
  `\{[a-z_]+\}`. Any match outside the closed set
  `{change_name, task_id, slug}` MUST trigger `status: blocked` with
  the canonical message `unknown placeholder {<token>} in commit format`
  naming the offending token. MUST NOT attempt `git commit`. Rationale:
  silent substitution of garbage keeps drift invisible, which is the
  exact failure this directive exists to fix.

## Loop

1. Run:

```bash
ai-harness task-next -c {change}
```

2. If no task is returned, write or update `implementation.md` and
   return `done`.
3. Implement exactly the returned task and its undone subtasks.
   TDD applies where tests exist or behavior is testable.
4. Run relevant tests and quality gates for the task.
5. Mark each completed subtask with:

```bash
ai-harness task-done -c {change} -i <id>
```

6. Make one commit for the task. **Apply the `commit-format` directive
   inlined in the delegation block above:** substitute `{change_name}`
   with the Change name, `{task_id}` with the task id, and `{slug}`
   with a slugified form of the task title (lowercase, hyphens for
   whitespace, ASCII-only). Substitution order is fixed:
   `{change_name}` → `{task_id}` → `{slug}` (slug is generated last
   so it cannot collide with literal `{change_name}` / `{task_id}`
   segments). Pass the substituted result as the single `-m`
   argument to `git commit`. After substitution, scan the result
   with the regex `\{[a-z_]+\}`; any match outside the closed set
   `{change_name, task_id, slug}` (for example a typo `{change}` or
   a future `{phase}`) MUST trigger `status: blocked` with the
   canonical message `unknown placeholder {<token>} in commit format`
   and MUST NOT attempt `git commit`. Do not combine multiple tasks
   into one commit.
7. Append the canonical `## Commits` line, then one matching
   `## TDD Evidence` row, to
   `.ai-harness/changes/{change}/implementation.md` atomically. The
   row's `(Task, Commit)` cells match the line just written.
8. Repeat while context and time allow. If tasks remain, return
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

Append exactly one row to `## TDD Evidence` for every `## Commits`
line, with every cell populated against the per-column grammar below.

`Remaining` is the canonical prose form of `semantic_facts.partial`
plus `semantic_facts.remaining_tasks`. Keep both aligned so resume can
recover them from disk.

## TDD evidence

The `## TDD Evidence` table is the **grammar source of truth** for
both this prompt and `change-validator.md`. The validator mirrors each
rule inline and references this prompt as authority — future grammar
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

### Loop step

Inside the loop, immediately after `ai-harness task-done` + `git
commit`, append the canonical `## Commits` line, then append one
matching row to `## TDD Evidence` with all ten cells populated against
the grammar above, BEFORE advancing to the next task. The row's
`Task` cell equals the task id from `task-list`; the `Commit` cell
equals the SHA just produced.

## Blocking

If you cannot proceed, stop before committing unrelated work. Leave
the working tree clean if possible and explain the blocker.

## Result

Return the **shared phase result envelope**:

```result
status:           done | partial | blocked
artifacts:        .ai-harness/changes/{change}/implementation.md
summary:          <one-line summary>
semantic_facts:
  partial:        <bool>
  remaining_tasks: <id[, id, ...]>
  changed_files:  <path[, path, ...]>
skills:           loaded | fallback | none
skill_resolution: ok | degraded: <reason>  (only when degraded)
```

- `status: done` — `task-next` returns nothing; all tasks closed and
  `implementation.md` reflects every commit.
- `status: partial` — tasks remain and `implementation.md` lists the
  remaining ids. The orchestrator re-invokes this implementor.
- `status: blocked` — explain the blocker in a brief prose note **before**
  the result block, then emit the block with
  `semantic_facts.blocked_reason: <text>`.

Skills and resolution:

- `skills: loaded` — every required `SKILL.md` path resolved and read.
- `skills: fallback` — at least one required skill could not be loaded;
  enumerate the fallback and explain in `skill_resolution`. Never invent
  a path.
- `skills: none` — this phase required no skills.
