# Spec — validator-tdd-evidence-audit

## Purpose

Lock the validator prompt's contract for auditing TDD evidence in
`implementation.md` and emitting the `## TDD Evidence Audit` summary in
`validation.md`. This covers section placement, the summary table header,
the textual cross-consistency checks between `task-list` / `## Commits` /
`## TDD Evidence`, the per-column grammar (mirrored from the implementor
prompt, which is the source of truth), the severity mapping as inline
policy, the rule that quality gates run literally from the target repo's
`CODING_STANDARDS.md` with no hardcoded commands, the audit summary's
mirroring of `fail`/`warn` rows into `## Findings`, and the textual-only
audit posture (no git history, no commit diffs, no test-source
inspection).

## Requirements

### Requirement: section-placed-after-gates
The validator MUST append a `## TDD Evidence Audit` section in
`validation.md` placed AFTER the existing `## Gates` section. The existing
sections (`## Verdict`, `## Coverage`, `## Findings`, `## Gates`) MUST
remain byte-identical to today's content except for the append described
here.

#### Scenario: section order in validation.md
GIVEN the rendered `validation.md` for any audited Change
WHEN a reviewer reads it top-to-bottom
THEN the section order is
`## Verdict`, `## Coverage`, `## Findings`, `## Gates`,
`## TDD Evidence Audit`
with no other sections interleaved.

### Requirement: summary-table-header
The `## TDD Evidence Audit` section MUST contain a Markdown table whose
header row is exactly `Check | Result | Details`, where
`Result ∈ {pass, fail, warn}`. The `Check` column MUST use a short stable
name from the fixed set
`section-present | cross-ref | no-duplicate | no-extra | grammar-red |
grammar-green | safety-net | test-coverage | layer | refactor |
gate-ownership | cell-count`.

#### Scenario: header text matches exactly
GIVEN the rendered `validation.md`
WHEN a reviewer greps for the `## TDD Evidence Audit` summary header row
THEN the line is exactly `| Check | Result | Details |` with no extra
columns, no reordered columns, no missing columns.

#### Scenario: row uses only permitted result values
GIVEN the audit emits a finding for the `grammar-red` check
WHEN the row is rendered into `validation.md`
THEN the row's `Result` cell is exactly `pass`, `fail`, or `warn` — no
other value is allowed in the audit table.

### Requirement: cross-consistency-audit
The validator MUST confirm, textually and against `implementation.md`
only, that:

- Every task id `ai-harness task-list` reports as `completed` appears in
  `## Commits`.
- Every such task id appears as the `Task` cell in exactly one
  `## TDD Evidence` row.
- Each row's `(Task, Commit)` pair appears in `## Commits`.
- No `(Task, Commit)` pair appears in more than one row (no duplicates).
- No row references a task id `task-list` reports as `pending` (no extra
  rows).

When parsing a `## Commits` line, the validator MUST read only the
`- <sha> — task <id>: <summary>` prefix; any trailing prose (including a
legacy `; tests: <commands>` segment or any parenthetical) is harmless
suffix noise and is ignored.

#### Scenario: completed task with no commit line
GIVEN `ai-harness task-list` reports task `t3` as `completed`
AND `## Commits` contains lines for `t1` and `t2` only
WHEN the validator runs the cross-consistency audit
THEN the audit emits a CRITICAL finding naming task `t3` with detail
"no `## Commits` line for completed task".

#### Scenario: completed task with no evidence row
GIVEN `ai-harness task-list` reports task `t3` as `completed`
AND `## TDD Evidence` contains rows for `t1` and `t2` only
WHEN the validator runs the cross-consistency audit
THEN the audit emits a CRITICAL finding naming task `t3` with detail
"no `## TDD Evidence` row for completed task".

#### Scenario: row references a Commit SHA not in ## Commits
GIVEN `## TDD Evidence` contains a row with `Commit: feedface` and
`Task: t3` AND `## Commits` does NOT contain `feedface`
WHEN the validator runs the cross-consistency audit
THEN the audit emits a CRITICAL finding naming the row's
`(Task, Commit)` pair with detail "Commit SHA not present in
`## Commits`".

#### Scenario: row Task cell does not match the commit line's task id
GIVEN `## TDD Evidence` contains a row with `Commit: abc1234` and
`Task: t9` AND `## Commits` contains `- abc1234 — task t3: ...`
WHEN the validator runs the cross-consistency audit
THEN the audit emits a CRITICAL finding with detail
"row Task `t9` does not match `## Commits` task id `t3`".

#### Scenario: duplicate rows
GIVEN `## TDD Evidence` contains two rows with the same
`(Task: t3, Commit: abc1234)`
WHEN the validator runs the cross-consistency audit
THEN the audit emits a CRITICAL finding with detail
"duplicate `## TDD Evidence` row for `(t3, abc1234)`".

#### Scenario: extra row for a pending task
GIVEN `ai-harness task-list` reports task `t9` as `pending`
AND `## TDD Evidence` contains a row with `Task: t9`
WHEN the validator runs the cross-consistency audit
THEN the audit emits a CRITICAL finding with detail
"extra `## TDD Evidence` row for pending task `t9`".

#### Scenario: legacy suffix on a clean Change produces no findings
GIVEN a Change whose `## Commits` lines all carry a legacy
`; tests: <commands>` suffix
AND every other check (cross-ref, no-duplicate, no-extra, grammar-*,
layer, refactor, gate-ownership, cell-count, section-present) is `pass`
WHEN the validator runs the full audit
THEN the audit emits no findings related to the suffix; the verdict is
`pass`.

### Requirement: column-grammar-mirrored-from-implementor
The validator prompt MUST inline its own copy of every per-column regex /
equality rule declared in the implementor prompt (Layer enum, RED literal,
GREEN literal, Triangulation regex, Safety net regex with `0 ≤ N ≤ M`,
Refactor two-value set `{clean, none needed}`, behavior-without-test
rule, cell-count rule). The validator prompt MUST reference
`change-implementor.md` as the grammar source of truth so future column
additions are localized to the two prompts.

#### Scenario: layer value inside enum
GIVEN a row with `Layer: unit`
WHEN the validator runs the column-grammar audit
THEN the `layer` check reports `pass`.

#### Scenario: layer value outside enum
GIVEN a row with `Layer: smoke`
WHEN the validator runs the column-grammar audit
THEN the `layer` check reports `warn` and the audit mirrors the result
into `## Findings` as a WARNING.

#### Scenario: RED cell equals the literal
GIVEN a row with `RED: written`
WHEN the validator runs the column-grammar audit
THEN the `grammar-red` check reports `pass`.

#### Scenario: RED cell off-grammar
GIVEN a row with `RED: drafted`
WHEN the validator runs the column-grammar audit
THEN the `grammar-red` check reports `fail` and the audit mirrors the
result into `## Findings` as a CRITICAL finding.

#### Scenario: GREEN cell equals the literal
GIVEN a row with `GREEN: passed`
WHEN the validator runs the column-grammar audit
THEN the `grammar-green` check reports `pass`.

#### Scenario: GREEN cell off-grammar
GIVEN a row with `GREEN: skipped`
WHEN the validator runs the column-grammar audit
THEN the `grammar-green` check reports `fail` and the audit mirrors the
result into `## Findings` as a CRITICAL finding.

#### Scenario: triangulation matches the regex
GIVEN a row with `Triangulation: 3 cases`
WHEN the validator runs the column-grammar audit
THEN the triangulation check reports `pass`.

#### Scenario: triangulation off-grammar
GIVEN a row with `Triangulation: many`
WHEN the validator runs the column-grammar audit
THEN the triangulation check reports `fail` and the audit mirrors the
result into `## Findings` as a CRITICAL finding.

#### Scenario: safety net matches the regex and the numeric invariant
GIVEN a row with `Safety net: passed: 3/3`
WHEN the validator runs the column-grammar audit
THEN the `safety-net` check reports `pass`.

#### Scenario: safety net has invalid numerator/denominator
GIVEN a row with `Safety net: passed: 5/3`
WHEN the validator runs the column-grammar audit
THEN the `safety-net` check reports `fail` and the audit mirrors the
result into `## Findings` as a CRITICAL finding.

#### Scenario: safety net for a new-file task
GIVEN a row where `Non-test files` and `Test files` are both empty (only
new files were created, no edits)
WHEN the implementor writes `Safety net: N/A: new files`
THEN the `safety-net` check reports `pass`.

#### Scenario: Refactor cell equals one of the two allowed values
GIVEN a row with `Refactor: clean`
WHEN the validator runs the column-grammar audit
THEN the `refactor` check reports `pass`.

#### Scenario: Refactor cell is empty
GIVEN a row with `Refactor:` (empty cell)
WHEN the validator runs the column-grammar audit
THEN the `refactor` check reports `warn` and the audit mirrors the
result into `## Findings` as a WARNING.

#### Scenario: Refactor cell uses the disallowed `deferred` value
GIVEN a row with `Refactor: deferred`
WHEN the validator runs the column-grammar audit
THEN the `refactor` check reports `warn` and the audit mirrors the
result into `## Findings` as a WARNING, because `deferred` is off-grammar
per the settled two-value contract.

#### Scenario: row claims behavior change but no test
GIVEN a row with `Non-test files: src/x.py` and `Test files: N/A`
WHEN the validator runs the column-grammar audit
THEN the `test-coverage` check reports `fail` and the audit mirrors the
result into `## Findings` as a CRITICAL finding titled
"behavior without test".

#### Scenario: row is a test-only change
GIVEN a row with `Non-test files:` (empty) and
`Test files: tests/test_x.py`
WHEN the validator runs the column-grammar audit
THEN the `test-coverage` check reports `pass`.

#### Scenario: row splits to exactly ten cells
GIVEN a well-formed row whose ten columns are separated by nine `|`
characters and no `|` appears inside any cell
WHEN the validator runs the column-grammar audit
THEN the `cell-count` check reports `pass`.

#### Scenario: row contains a stray pipe inside a cell
GIVEN a row that, due to a stray `|` inside a cell, splits to eleven
cells
WHEN the validator runs the column-grammar audit
THEN the `cell-count` check reports `fail` and the audit mirrors the
result into `## Findings` as a CRITICAL finding.

### Requirement: severity-mapping-locked-inline
The validator MUST classify conditions and mirror each into `## Findings`
under the matching severity, with the mapping locked inline in the
validator prompt (not in a config file or Python module). Any future
relaxation is a prompt diff and is reviewable.

CRITICAL conditions:

- `RED` cell off-grammar (not equal to `written`).
- `GREEN` cell off-grammar (not equal to `passed`).
- `Safety net` cell contradicts its column grammar (regex mismatch,
  `N > M`, missing fraction, etc.).
- `Test files == "N/A"` while the same row's `Non-test files` is
  non-empty (behavior change without a test).
- Missing `## TDD Evidence` row for a completed task.
- Duplicate `## TDD Evidence` row (same `(Task, Commit)` pair).
- Extra `## TDD Evidence` row referencing a task `task-list` reports as
  `pending`.
- Row references a `Commit` SHA not present in any `## Commits` line.
- Row's `Task` cell is not in `ai-harness task-list` at all.
- Gate failure on a file listed in any row's `Non-test files` or
  `Test files` cells (row claims ownership).

WARNING conditions:

- `Refactor` cell empty or off-grammar (any value other than `clean` or
  `none needed`, including `deferred`, `in-progress`, blank, etc.).
- `Layer` cell outside the enum
  `{unit, integration, e2e, mixed, N/A}`.
- Gate failure on a file NOT listed in any row's `Non-test files` or
  `Test files` cells.

The implementor prompt MUST mirror only the column grammar, NOT the
severity mapping. Severity is the validator's policy authority.

#### Scenario: only Refactor is off-grammar
GIVEN every check `pass` or `warn` and only one WARNING under
`## Findings` (for `Refactor`)
WHEN the validator sets the verdict
THEN `## Verdict` is `pass-with-warnings` AND `critical: 0`.

#### Scenario: WARNING-only audit does not block archive
GIVEN `## Findings` contains only WARNING-severity entries that
originate from the TDD audit
WHEN the orchestrator routes the Change
THEN archive proceeds (verdict `pass-with-warnings`, `critical: 0`).

### Requirement: gates-run-literally-from-coding-standards
The validator prompt MUST instruct the validator to read the target
repo's `CODING_STANDARDS.md` and run each required gate from there
literally. The prompt MUST NOT hardcode any gate command (no `ruff …`,
no `pylint …`, no `pytest …`, etc., inlined as a fixed command list).
Conditional language in `CODING_STANDARDS.md` (e.g. "if X then run Y",
"only when Z") MUST be respected exactly as written.

#### Scenario: standards list gates A, B, C
GIVEN the target repo's `CODING_STANDARDS.md` declares three required
gates named A, B, C (with whatever exact commands and conditional
language the standards declare)
WHEN the validator runs the gates section of the audit
THEN the validator runs exactly the commands declared in
`CODING_STANDARDS.md` for A, B, C, in the order declared, with conditional
language respected, and does NOT run any other command.

#### Scenario: no hardcoded commands in either prompt
GIVEN the rendered `change-validator.md` and `change-implementor.md`
prompts
WHEN a reviewer greps for hardcoded gate commands (e.g. literal `ruff`,
`pylint`, `pytest`, `mypy` invocations presented as fixed lists)
THEN no hardcoded command list is present in either prompt; the only
instruction is to read `CODING_STANDARDS.md` literally.

### Requirement: gate-failure-ownership-classifier
The validator MUST build the union of every row's `Non-test files` and
`Test files` cells (after deduplication) and classify each gate failure
by membership in that union: gate failure on a file listed in any row's
`Non-test files` or `Test files` is CRITICAL under `gate-ownership`;
gate failure on a file NOT listed in any row's column lists is WARNING.

#### Scenario: gate failure on a row-owned file
GIVEN `## TDD Evidence` contains a row with
`Non-test files: src/x.py` and `Test files: tests/test_x.py`
AND running the standards' gate against `src/x.py` reports a failure
WHEN the validator runs the gate-classification step
THEN the `gate-ownership` check reports `fail` and the audit mirrors the
result into `## Findings` as a CRITICAL finding naming `src/x.py`.

#### Scenario: gate failure on a non-row-owned file
GIVEN `## TDD Evidence` contains a row with
`Non-test files: src/x.py` and `Test files: tests/test_x.py`
AND running the standards' gate against `src/legacy/y.py` (NOT listed in
any row's column) reports a failure
WHEN the validator runs the gate-classification step
THEN the `gate-ownership` check reports `warn` and the audit mirrors the
result into `## Findings` as a WARNING naming `src/legacy/y.py` and
noting it was not claimed by any row.

#### Scenario: same gate failure on a union-listed file across multiple rows
GIVEN two rows both list `src/x.py` in their `Non-test files` cells
AND running the standards' gate against `src/x.py` reports a single
failure
WHEN the validator runs the gate-classification step
THEN exactly one CRITICAL finding is emitted naming `src/x.py`
(de-duplicated, not one finding per row).

### Requirement: textual-only-audit-posture
The validator MUST perform every audit check textually, against the
contents of `implementation.md`. The validator MUST NOT:

- invoke `git rev-parse`, `git log`, `git cat-file`, or any equivalent to
  verify commit SHAs exist in the repo's history;
- invoke `git diff`, `git show`, or any equivalent to inspect commit
  contents or re-derive RED/GREEN from the diff;
- re-run implementor-reported test commands verbatim; the gates that
  count come from `CODING_STANDARDS.md`;
- open, read, parse, or evaluate any test file referenced by a
  `## TDD Evidence` row. RED and GREEN cells are checked as literal
  strings only.

#### Scenario: audit does not touch git
GIVEN a `## TDD Evidence` row whose `Commit` SHA does not exist in
`git log` (but DOES appear in `## Commits`)
WHEN the validator runs the cross-consistency audit
THEN the audit reports `pass` for `cross-ref` and does NOT emit a finding
about the SHA's absence from git history.

#### Scenario: validator does not derive RED/GREEN from commit diffs
GIVEN a `## TDD Evidence` row with `RED: written` and `GREEN: passed`
AND the underlying commit diff is empty (no test changes)
WHEN the validator audits the row
THEN the audit reports `pass` for `grammar-red` and `grammar-green` based
solely on the cell values; the audit does NOT inspect the commit diff.

#### Scenario: implementor reports a different command
GIVEN `implementation.md` contains a `## Commits` line with a trailing
`; tests: pytest tests/test_x.py -k slow` legacy suffix
AND `CODING_STANDARDS.md` declares the required gate to be
`pytest tests/`
WHEN the validator runs the gates section
THEN the validator runs `pytest tests/` (from `CODING_STANDARDS.md`) and
does NOT run `pytest tests/test_x.py -k slow`.

#### Scenario: literal-string pass on a malformed assertion
GIVEN a row with `RED: written` and `GREEN: passed`
AND the underlying test file contains a malformed assertion
(e.g. `assert x ==` with no expected value, or `assert` with no argument)
WHEN the validator runs the audit
THEN the audit reports `pass` for `grammar-red` and `grammar-green` based
solely on the cell values; no finding is emitted about assertion quality.

### Requirement: mirror-failed-checks-into-findings
Every audit row whose `Result` is `fail` or `warn` MUST be mirrored into
the existing `## Findings` section under the matching severity
(`fail → CRITICAL`, `warn → WARNING`). Every `pass` row MUST NOT be
mirrored into `## Findings`. This is what keeps existing archive
routing — which keys off `verdict` / `critical` from `## Verdict` —
working unchanged.

The `Details` cell of each audit row MUST carry enough information for a
reviewer to identify what failed without re-reading `implementation.md`:
the row index or task id, the cell name when the failure is cell-scoped,
and the file path when the failure is file-scoped.

#### Scenario: fail row mirrored as CRITICAL
GIVEN the audit emits a `fail` row for `cell-count` on row 2
WHEN the auditor writes `validation.md`
THEN `## Findings` contains a CRITICAL entry whose text matches the
audit row's `Details`.

#### Scenario: warn row mirrored as WARNING
GIVEN the audit emits a `warn` row for `refactor` on row 2
WHEN the auditor writes `validation.md`
THEN `## Findings` contains a WARNING entry whose text matches the audit
row's `Details`.

#### Scenario: pass row not mirrored
GIVEN the audit emits a `pass` row for `cross-ref`
WHEN the auditor writes `validation.md`
THEN `## Findings` does NOT contain an entry mirroring that audit row.

#### Scenario: file-scoped detail
GIVEN the audit emits a CRITICAL `gate-ownership` finding for `src/x.py`
WHEN the row is rendered
THEN `Details` includes the file path `src/x.py`.

### Requirement: self-checklist-tail
The `## TDD Evidence Audit` section MUST end with a self-checklist tail
that enumerates every check name from the fixed set
`section-present | cross-ref | no-duplicate | no-extra | grammar-red |
grammar-green | safety-net | test-coverage | layer | refactor |
gate-ownership | cell-count`. The validator MUST tick off (or explicitly
call out missing) every check in its own output so a missed step is
visible to a reviewer reading `validation.md`.

#### Scenario: self-checklist lists every check
GIVEN the rendered `## TDD Evidence Audit` tail in `validation.md`
WHEN a reviewer reads the tail
THEN every check name from the fixed set appears at least once, either as
a ticked-off `pass` row above or as an explicit entry in the checklist.

#### Scenario: a missing check is visible in the output
GIVEN the auditor forgot to run the `cell-count` check
WHEN the auditor writes `validation.md`
THEN the self-checklist tail contains an explicit "missing: cell-count"
line so a reviewer sees the omission without running the audit
themselves.

### Requirement: result-envelope-and-routing-untouched
The validator prompt MUST keep the existing result envelope
(`status:`, `artifacts:`, `summary:`, `semantic_facts:`, `skills:`,
`skill_resolution:`) byte-identical to today's content; only the new
`## TDD Evidence Audit` section template is added. `## Verdict` and the
`verdict:` / `critical:` envelope fields MUST continue to drive archive
routing; the introduction of `## TDD Evidence Audit` MUST NOT introduce a
parallel routing path.

#### Scenario: envelope labels unchanged
GIVEN the pre-Change rendered validator prompt
WHEN the post-Change rendered validator prompt is diffed against the
pre-Change
THEN every line that contributed to a substring match against the
renderer test labels (`verdict:`, `critical:`) and the shared envelope
shape is unchanged.

#### Scenario: routing reads from ## Verdict
GIVEN a Change whose `## Verdict` is `pass-with-warnings` with
`critical: 0` AND whose `## TDD Evidence Audit` contains a `warn` row
WHEN the orchestrator routes the Change
THEN routing treats the Change as `pass-with-warnings` (NOT as a failure)
because the CRITICAL count is zero, exactly as today.