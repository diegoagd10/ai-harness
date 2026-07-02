# Spec — implementor-tdd-evidence-contract

## Purpose

Lock the implementor prompt's contract for writing TDD evidence into
`implementation.md` so the validator can audit it. This covers the canonical
`## Commits` line, the `## TDD Evidence` table with its ten-column header,
the per-column value grammar (source of truth for both prompts), the loop
instruction that appends one row per commit, the backward-compatible legacy
suffix treatment, and the rule that the implementor stays silent on skill
loading.

This is the implementor's half of the evidence contract. The validator's half
(`validator-tdd-evidence-audit`) reads what this capability emits and audits it
textually.

## Requirements

### Requirement: canonical-commit-line-form
The implementor prompt MUST instruct that each `## Commits` line is written
in exactly this prefix form:

`- <sha> — task <id>: <summary>`

where `<sha>` is the full commit SHA, `<id>` is the task id from
`ai-harness task-list`, and `<summary>` is a short human-readable summary.
No alternate format is shown as a template.

#### Scenario: implementor writes a canonical line
GIVEN a completed task `t3` with summary `add evidence row` and a commit SHA
`deadbeef`
WHEN the implementor appends a `## Commits` line for that task
THEN the line is `- deadbeef — task t3: add evidence row`
(em-dash separator, single space on each side, `task ` prefix on the id,
colon between id and summary, no surrounding whitespace beyond a single
leading hyphen).

#### Scenario: prefix form is the only template shown
GIVEN the rendered implementor prompt's loop block
WHEN a reviewer greps for `## Commits` examples or templates
THEN every example or template matches the canonical prefix form
`- <sha> — task <id>: <summary>`.

### Requirement: legacy-suffix-is-noise-not-template
The implementor prompt MUST NOT emit a legacy `; tests: <commands>` segment
as part of the canonical line. The prompt MUST include a short note that
any trailing `; tests:` prose on a commit line is harmless suffix noise
ignored by the validator at audit time. The canonical example MUST NOT
contain `; tests:`.

#### Scenario: canonical example excludes the suffix
GIVEN the rendered implementor prompt's loop block
WHEN a reviewer greps for the canonical line example
THEN the example line ends after the summary text and does NOT contain
`; tests:`.

#### Scenario: validator-ignores-suffix note is present
GIVEN the rendered implementor prompt
WHEN a reviewer reads the prose near the `## Commits` instruction
THEN a short note exists stating that any trailing `; tests: <commands>`
prose on a commit line is harmless suffix noise ignored by the validator.

### Requirement: ten-column-header-in-order
The implementor prompt MUST inline a `## TDD Evidence` table whose header
row is exactly the ten columns, in this order:

`Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor`

#### Scenario: header text matches exactly
GIVEN the rendered `change-implementor.md` prompt
WHEN a reviewer greps for the `## TDD Evidence` section header row
THEN the line is exactly
`| Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor |`
with no extra columns, no reordered columns, no missing columns.

### Requirement: per-column-value-grammar
The implementor prompt MUST inline the per-column value grammar verbatim
and MUST be the source of truth that both prompts reference. The grammar is:

- `Task` — task id from `ai-harness task-list`.
- `Commit` — full SHA from the commit just made.
- `Non-test files` — comma-separated paths, single line, no `|`.
- `Test files` — same shape; `N/A` allowed only when `Non-test files` is
  empty.
- `Layer` ∈ `{unit, integration, e2e, mixed, N/A}`.
- `Safety net` matches `^(passed: N/M|N/A: new files|N/A: .+)$` with
  `0 ≤ N ≤ M`.
- `RED` literal `written`.
- `GREEN` literal `passed`.
- `Triangulation` matches `^(N cases|Single|N/A: .+)$`.
- `Refactor` ∈ `{clean, none needed}`. `deferred` and any other value are
  NOT permitted and are off-grammar WARNING.

No `|` may appear inside any cell — pipes break Markdown table parsing.

#### Scenario: all ten cells present on a clean task
GIVEN a completed task that wrote one non-test file `src/x.py`, one test
file `tests/test_x.py`, and ran one safety-net pass
WHEN the implementor appends the evidence row
THEN every one of the ten cells is non-empty and matches the grammar above
(including `Layer: unit`, `RED: written`, `GREEN: passed`,
`Triangulation: Single`, `Safety net: passed: 1/1`, and
`Refactor: clean` or `Refactor: none needed`).

#### Scenario: no pipe character inside any cell
GIVEN the implementor is composing a row whose `Non-test files` cell would
list two paths
WHEN the row is written into `implementation.md`
THEN the two paths are comma-separated inside a single cell
(`src/x.py, src/y.py`), NOT pipe-separated across cells, so the table
parses to exactly ten columns.

#### Scenario: Refactor uses only the two allowed values
GIVEN the implementor is composing a row's `Refactor` cell
WHEN the implementor writes the cell
THEN the value is exactly `clean` or `none needed`. The value `deferred` is
NOT permitted; writing it produces a Refactor WARNING on audit. Writing
any other value (including `in-progress`) also produces a Refactor WARNING.

### Requirement: row-per-completed-task-commit
The implementor prompt MUST instruct that, immediately after each
`ai-harness task-done` + `git commit` step inside the TDD loop, the
implementor appends exactly one row to the `## TDD Evidence` table in
`implementation.md` BEFORE advancing to the next task. The appended row's
`Task` cell MUST equal the task id reported by `ai-harness task-list` for
that task, and the row's `Commit` cell MUST equal the full SHA of the
commit just produced.

#### Scenario: clean one-task Change
GIVEN a Change with one task `task-list` reports as completed and one
commit whose SHA is `abc1234`
WHEN the implementor finishes the loop for that task
THEN `implementation.md` contains exactly one `## TDD Evidence` row whose
`Task` cell is the task id and whose `Commit` cell is `abc1234`.

#### Scenario: no row is appended without a commit
GIVEN the implementor is mid-loop but has not yet produced a commit for
the current task
WHEN the implementor advances the loop past that task
THEN no `## TDD Evidence` row is appended (rows exist only after commits).

### Requirement: loop-instruction-placed-next-to-commit-line
The implementor prompt MUST place the "append one matching
`## TDD Evidence` row after each `task-done` + commit step" instruction
inside the TDD loop block, adjacent to the existing commit-line
instruction, so a single read of the loop covers both writes. The order
within the loop body MUST be: commit line first, then evidence row, then
the loop-control text that advances to the next task.

#### Scenario: loop block contains both writes in order
GIVEN the rendered TDD loop block in the implementor prompt
WHEN a reviewer reads the loop from top to bottom
THEN both the `## Commits` line instruction and the `## TDD Evidence`
row instruction appear in the loop body, in that order, before the
loop-control text that advances to the next task.

### Requirement: implementor-silent-on-skill-loading
The implementor prompt MUST NOT contain prose that re-loads or re-injects
the TDD skill. Skill injection is the orchestrator's responsibility. This
keeps the implementor from duplicating the orchestrator's injection
boundary.

#### Scenario: no skill-load prose in implementor prompt
GIVEN the rendered `change-implementor.md` prompt
WHEN a reviewer searches for any prose instructing the implementor to load
or inject a skill (TDD or otherwise)
THEN no such prose is found.

### Requirement: result-envelope-and-remaining-untouched
The implementor prompt MUST keep `## Remaining` and the existing result
envelope (`status:`, `artifacts:`, `summary:`, `semantic_facts:`,
`skills:`, `skill_resolution:`) byte-identical to today's content; only
the new `## TDD Evidence` table template and the loop-instruction append
are added.

#### Scenario: envelope labels unchanged
GIVEN the pre-Change rendered implementor prompt
WHEN the post-Change rendered implementor prompt is diffed against the
pre-Change
THEN every line that contributed to a substring match against the renderer
test labels (`partial:`, `changed_files:`, `remaining_tasks:`) is
unchanged.