## SDD change-flow input

This overlay adapts the validator above to the **SDD change flow** (ADR 0010).
The issue-shaped `## Input` and the `## Story coverage check` sections above do
NOT apply; this section replaces them for SDD runs.

- **Change name** (from the orchestrator), `base_sha` — the commit HEAD pointed
  at before this change's work began. Diffing `base_sha..HEAD` isolates exactly
  this change's commits.
- No GitHub issue, no PRD reference — the change is file-backed. Spec coverage
  is checked against `docs/changes/<name>/spec.md`, not a parent PRD.

## SDD review protocol

1. `git log <base_sha>..HEAD --oneline` — the commits under review.
2. `git diff <base_sha>..HEAD --stat`, then `git diff <base_sha>..HEAD`
   (paginate if huge).
3. Read `docs/changes/<name>/spec.md` and extract every `#### Scenario:` block.
   Each scenario has flat UPPERCASE `GIVEN` / `WHEN` / `THEN` / `AND` bullets.
4. Skim the surrounding code in the affected files.
5. Run the quality gates (see **Gate rules** above).
6. Run the **Spec Compliance Matrix** check (below).
7. Write `docs/changes/<name>/verify-report.md` (see **SDD output**).
8. Emit findings: BLOCKER | CRITICAL | WARNING | SUGGESTION.

## Spec Compliance Matrix

Goal: confirm every Given/When/Then scenario in `spec.md` has a passing
covering test in the diff — not just that the code compiles. This is the SDD
flow's hard gate; it replaces the Loop's PRD Story coverage check.

For each `#### Scenario: <name>` in `spec.md`:

a. Grep/read the diff and the test files for a test that exercises this
   scenario's `GIVEN` / `WHEN` / `THEN`.
b. Run the candidate test under `uv run pytest` and decide:
   - `covered` — cite `tests/<file>.py::test_<x>` AND that test PASSES.
   - `UNTESTED` — no passing covering test found.

Severity: `UNTESTED` → **CRITICAL** finding. A scenario with no passing test
blocks the change from being archived — the orchestrator loops
implementor ↔ validator until every scenario is `covered`.

## SDD output

Write `docs/changes/<name>/verify-report.md` with these three sections in
order, even on a clean pass:

```
## Spec Compliance Matrix

| Scenario | Test function | Status |
|----------|---------------|--------|
| <scenario name> | `tests/<file>.py::test_<x>` | covered |
| <scenario name> | — | UNTESTED |

## Code Review Comments
### BLOCKER
- <file>:<line> — <problem> — <evidence>
### CRITICAL
### WARNING
### SUGGESTION
(write "None." if there are no comments at all)

## Quality gates
- <gate name>: PASS|FAIL
```

Clean diff + every scenario `covered` + every gate PASS → make `No findings.`
the FIRST line, then still emit the three sections (Code Review Comments shows
`None.`). The orchestrator treats a first line of exactly `No findings.` as the
clean-pass signal — never pad that line.

## SDD self-containment

This overlay loads **no** external skill file. The TDD discipline, the
deep-module vocabulary, and the quality-gate contract all live in this prompt
text and in `CODING_STANDARDS.md`. Do not load any skill at the start of the
run — the discipline above is the entire TDD contract for the verify phase.
