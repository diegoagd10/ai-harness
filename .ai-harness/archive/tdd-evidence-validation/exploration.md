# Exploration — tdd-evidence-validation

## Budget

100

## Affected Files

- `src/ai_harness/resources/change-agent/change-implementor.md` — re-shape `## Commits` line template, add `## TDD Evidence` table mandate, add the loop instruction that every commit step appends one matching evidence row, and inline the column-value contract (Layer, RED, GREEN, Triangulation, Safety net, Refactor). Keep `## Remaining` and the existing result envelope intact.
- `src/ai_harness/resources/change-agent/change-validator.md` — keep `## Verdict`, `## Coverage`, `## Findings`, `## Gates`; add `## TDD Evidence Audit` with a `Check | Result | Details` summary table at the end so archive routing still keys off `critical`. Inline the audit rules (row↔commit↔task cross-reference, no duplicates/extras, column grammar, severity mapping).
- `tests/test_renderers.py` — investigated, NOT touched. The existing renderer tests only lock envelope field labels (`partial:`, `changed_files:`, `remaining_tasks:` for the implementor; `verdict:`, `critical:` for the validator) and the shared envelope shape (`status:`, `artifacts:`, `summary:`, `semantic_facts:`, `skills:`, `skill_resolution`). They do NOT snapshot full prompt bodies, so adding new sections is safe. Mentioned here so the implementor knows to re-run the renderer test gate after editing.

No changes to:
- `src/ai_harness/modules/harness/tdd_evidence.py` — removed from scope. The audit logic lives in the validator's prompt, not in a Python module.
- `tests/test_tdd_evidence.py` — removed from scope; there is no Python audit module to test.
- `src/ai_harness/resources/change-agent/change-orchestrator.md` — the orchestrator already injects the TDD skill into the implementor (orchestrator line ~332: "**`change-implementor` always receives the TDD skill.**"). The orchestrator stays silent on skill expectations; injection is its boundary.
- CLI surface — no new `ai-harness validate-tdd` subcommand in v1.

## Plan

1. **Implementor prompt rework** (`change-implementor.md`):
   - Replace the `## Commits` line template with `- <sha> — task <id>: <summary>` (drop `; tests: <commands>` from the canonical example; explain that any trailing `; tests:` prose is treated as harmless suffix noise by the validator and ignored on audit).
   - Add a `## TDD Evidence` section to the structure template: a Markdown table with the exact ten columns `Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor`.
   - Add a loop instruction in the Loop block: after every `ai-harness task-done` + commit step, append one matching `## TDD Evidence` row before moving on. The row appears BEFORE the next `## Commits` line in `implementation.md`.
   - Inline the column-value contract verbatim from the shared understanding: `Layer ∈ {unit, integration, e2e, mixed, N/A}`; `RED == "written"` (the literal string); `GREEN == "passed"` (the literal string); `Triangulation` matches `^(N cases|Single|N/A: .+)$`; `Safety net` matches `^(passed: \d+/\d+|N/A: new files|N/A: .+)$`; `Refactor ∈ {clean, none needed, deferred}`.
   - Do NOT inject or re-load the TDD skill in this prompt. The orchestrator owns the injection; the implementor stays silent on skills.

2. **Validator prompt rework** (`change-validator.md`):
   - Keep the existing four sections: `## Verdict`, `## Coverage`, `## Findings`, `## Gates`. Append `## TDD Evidence Audit` AFTER `## Gates` so archive routing still depends on `verdict` / `critical` from `## Verdict`.
   - Add the audit summary table: columns `Check | Result | Details`, where Result is `pass` | `fail` | `warn`. Every failed check is also appended to `## Findings` under the matching severity so the existing CRITICAL-driven archive logic keeps working unchanged.
   - Inline the textual checks:
     - Every completed task from `ai-harness task-list` has a row in BOTH `## Commits` AND `## TDD Evidence`.
     - Each row's `Task` and `Commit` values match a `## Commits` entry EXACTLY.
     - No duplicate rows (same `(Task, Commit)` pair).
     - No extra rows (a row referencing a Task that `task-list` reports as `pending`).
     - Column values follow the column grammar listed above.
   - Spell out the severity mapping inline: `RED` violation, `GREEN` violation, `Safety net` contradiction, `Test files == "N/A"` while non-test files exist, missing row for a completed task, duplicate row, extra row, commit SHA not in `## Commits`, task id not in `task-list` → all CRITICAL. `Refactor` violation → WARNING. Gate-failure classification is left as WARNING-by-default unless the gate-failed files are listed in the row's `Non-test files` or `Test files` columns, in which case the gate failure is CRITICAL (the row claims ownership).
   - Explicitly instruct the validator to run the required quality gates from `CODING_STANDARDS.md` literally, and NEVER inspect commit diffs, rerun implementor-reported test commands, or verify git SHAs exist in the repo. The validator reads `implementation.md` and runs the gates; it does not verify git history.
   - Explicitly state: no assertion-quality audit in v1. The validator confirms that RED and GREEN cells contain the expected literal strings, not that the assertions are well-formed.

3. **Renderer test gate** (no edit, just a regression check):
   - After editing the two prompts, run `uv run pytest tests/test_renderers.py` to confirm envelope field labels (`partial:`, `changed_files:`, `remaining_tasks:` for the implementor; `verdict:`, `critical:` for the validator) and shared envelope shape still pass. These tests are substring/contains checks on the rendered prompt body, so they tolerate new sections without snapshot drift.

## Edge Cases

- `## TDD Evidence` section missing entirely from `implementation.md` (older Changes predate this contract): CRITICAL "TDD evidence section missing" for the Change, but keep backward compatibility with `## Commits` legacy `; tests:` suffix lines (parse the prefix, ignore the suffix).
- A completed task has no `## Commits` entry: CRITICAL (already covered by today's coverage gate).
- A completed task has a `## Commits` entry but no `## TDD Evidence` row: CRITICAL per task id.
- A `## TDD Evidence` row exists for a `Task` id that `task-list` reports as `pending`: CRITICAL "extra row".
- Two rows in `## TDD Evidence` reference the same `(Task, Commit)` pair: CRITICAL duplicate.
- A row's `Commit` SHA does not appear in `## Commits`: CRITICAL. The validator does NOT verify the SHA exists in git — only that it appears in `## Commits`.
- `Layer` cell uses a value outside the enum (e.g. `unit`, `integration`, `e2e`, `mixed`, `N/A` only): WARNING (parser-recognizable but off-contract).
- `RED` cell ≠ `written`, or `GREEN` cell ≠ `passed`: CRITICAL.
- `Test files` cell is `N/A` while the task's `Non-test files` cell is non-empty: CRITICAL "behavior without test".
- `Safety net` cell is blank, off-grammar (`passed: 3/2` is invalid because denominator must be ≥ numerator and both must be ≥ 0), or contradicts the column grammar: CRITICAL.
- `Refactor` cell is empty or off-grammar: WARNING.
- Multi-line cell content (file list with commas inside a single cell): the implementor's table renders each cell as a single line; cells containing `|` are forbidden because they break Markdown table parsing.
- Subtasks: one row per completed top-level task commit. Subtask commits are NOT part of the v1 contract.
- Backward-compatible `## Commits` line noise (`; tests: pytest …`): validator parses the prefix `- <sha> — task <id>: <summary>` and ignores trailing prose.
- Gate failure on a file NOT listed in any `Non-test files` or `Test files` cell: WARNING (pre-existing / unrelated). Gate failure on a file listed in the row's columns: CRITICAL (row claims ownership).

## Test Surface

- `uv run pytest tests/test_renderers.py` — regression gate. Confirms envelope field labels and shared envelope shape survive the prompt edits. No new tests authored; the renderer tests are tolerance-based (substring checks), so adding new sections does not break them.
- `uv run pytest tests/test_install.py` — sanity check that agent-rendering/install does not regress when the two prompts change (frontmatter is untouched, only body sections are added).
- Required repo gates from `CODING_STANDARDS.md`: `ruff format --check`, `ruff check`, `pylint duplicate-code`, `pytest`. No conditional e2e (no diff to `e2e/` or install/uninstall paths in v1).
- Prompt files are Markdown content, not Python. They are validated by re-reading the contract sections, not by automated snapshot tests. A grep-based lint (manual or future linter) can confirm the column header is exactly the ten-column string in `change-implementor.md` and the audit table column header is exactly `Check | Result | Details` in `change-validator.md`.

## Risks

- **Backward compatibility with existing Changes**: any in-flight `implementation.md` predating this contract will fail TDD audit by design. Mitigation: document that this Change is opt-in for future Changes; existing Changes complete with the old contract are not retroactively validated unless re-implemented.
- **Column grammar drift**: future contributors adding new column values (e.g. `Refactor: in-progress`) without updating the contract would silently WARNING or fail in unexpected ways. Mitigation: keep all column-value grammars centralized as inline constants in `change-implementor.md`; reference the implementor prompt as the source of truth in `change-validator.md` so future column additions are localized to two prompts.
- **Skill injection boundary drift**: if a future prompt edit re-introduces TDD skill loading text in `change-implementor.md`, it duplicates the orchestrator's injection. Mitigation: leave the implementor prompt silent on skill loading (it already is today); add an inline note in the validator prompt that the orchestrator owns skill injection.
- **Parse ambiguity on pipe `|` inside cells**: cells like `Non-test files: src/x.py | src/y.py` would break Markdown table parsing. Mitigation: the implementor's template explicitly forbids `|` inside cells; the validator's parse step uses a counted split equal to the column count and surfaces CRITICAL on cell-count mismatch.
- **Audit table placement**: putting `## TDD Evidence Audit` after `## Gates` (not before `## Findings`) is intentional so archive routing continues to depend on `verdict` / `critical` from `## Verdict`. Mitigation: every failed audit check is ALSO appended to `## Findings` under the matching severity so the existing CRITICAL-driven archive logic keeps working unchanged.
- **Gate-failure classification is fuzzy**: distinguishing "implementor-owned file" vs "pre-existing" requires file ownership heuristics the validator cannot reliably compute in general. Mitigation: keep the classifier simple — compare gate-failure files against the union of `Non-test files` and `Test files` cells for the Change; anything else falls to WARNING.
- **Severity policy creep**: future contributors may push `Refactor` to CRITICAL or relax a CRITICAL rule. Mitigation: lock the severity mapping inline in `change-validator.md`; the implementor prompt mirrors the grammar but the validator prompt is the policy authority.
- **No automated regression for audit rules**: the audit rules are inline prose in `change-validator.md`, not code. A typo or omitted rule only surfaces at audit time. Mitigation: add a short checklist at the bottom of `## TDD Evidence Audit` that the validator must tick off, so a missing step is visible in the validator's own output rather than only to a reviewer.