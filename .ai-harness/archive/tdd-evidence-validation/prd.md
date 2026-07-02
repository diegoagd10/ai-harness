# PRD — tdd-evidence-validation

## Intent

The change-agent loop runs implementor + validator on every Change. Today nothing forces the
implementor to actually drive work test-first, and nothing forces the validator to confirm it
did. Reviewers discover skipped TDD by reading diffs after the fact, by which point the
opportunity to course-correct during the loop is gone.

This Change adds a **structured evidence contract** that the implementor writes and the
validator audits:

- A new `## TDD Evidence` table in `implementation.md`, one row per completed task commit,
  locking down red/green/safety-net/triangulation/refactor per task.
- A `## TDD Evidence Audit` summary in `validation.md`, produced from textual checks against
  `implementation.md` and the project's `CODING_STANDARDS.md`.

Adopted from Gentle AI's Strict TDD audit pattern. Outcome: a validator pass that is
verdict-only ("looks fine") becomes evidence-backed ("every task has a passing RED→GREEN
path tied to commits and a clean safety net"). Bad-TDD Changes stop passing silently.

## Scope

### In

- Updating `src/ai_harness/resources/change-agent/change-implementor.md` so the implementor:
  - Emits `## Commits` lines in the canonical form `- <sha> — task <id>: <summary>`.
  - Emits a `## TDD Evidence` Markdown table with exactly these columns, in this order:
    `Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor`.
  - Appends one matching `## TDD Evidence` row inside the TDD loop, immediately after each
    `ai-harness task-done` + commit step.
  - Keeps `## Remaining` and the existing result envelope untouched.
- Updating `src/ai_harness/resources/change-agent/change-validator.md` so the validator:
  - Reads `implementation.md` and audits textual cross-consistency between
    `ai-harness task-list`, `## Commits`, and `## TDD Evidence`.
  - Runs required quality gates from the target repo's `CODING_STANDARDS.md` literally,
    no hardcoded command list.
  - Appends a `## TDD Evidence Audit` section (placed AFTER `## Gates`) with a
    `Check | Result | Details` summary table.
  - Mirrors every failed audit check into `## Findings` with the correct severity, so
    archive routing still keys off `verdict` / `critical`.
- Running the existing `tests/test_renderers.py` (and `tests/test_install.py`) as
  regression gates. No new product-Python module, no new CLI subcommand, no new audit
  module, no new test file required for the audit logic.

### Out

- Any new Python module under `src/ai_harness/modules/harness/` (including a
  `tdd_evidence.py` parser or auditor).
- Any new CLI subcommand (`ai-harness validate-tdd` or similar).
- Any new test file under `tests/` for the audit rules themselves; the renderer tests are
  tolerance-based (substring checks) and are sufficient regression coverage.
- Any change to `change-orchestrator.md` — the orchestrator already injects the TDD skill
  into the implementor and stays the owner of skill-injection rules. The implementor stays
  silent on skill loading to avoid duplication.
- Verifying commit SHAs exist in the git history; the validator is textual-only.
- Re-running implementor-reported test commands verbatim; the validator runs the
  authoritative gates from `CODING_STANDARDS.md`.
- Inspecting commit diffs or in any way re-deriving RED/GREEN from git.
- An assertion-quality audit (checking whether the test assertions are well-formed).
  RED/GREEN cells are confirmed against expected literal values only.
- Subtasks: a separate audit row per subtask commit. v1 is one row per top-level
  completed task commit.
- Retroactive audit of in-flight `implementation.md` files that predate this contract;
  this Change is opt-in for future Changes.

## Capabilities

- **implementor-emits-tdd-evidence-row**: For every `ai-harness task-done` + commit step
  inside the implementor TDD loop, the implementor appends exactly one `## TDD Evidence`
  row whose `Task` and `Commit` cells match the `## Commits` line just written. All ten
  column cells are populated against the inline grammar before the loop advances.
- **implementor-canonical-commit-line**: The implementor writes `## Commits` lines in the
  canonical form `- <sha> — task <id>: <summary>`. Any legacy trailing `; tests: <commands>`
  prose left by older prompts is treated as harmless suffix noise and is ignored by the
  validator at audit time.
- **validator-evidence-cross-consistency**: The validator confirms that every completed
  task reported by `ai-harness task-list` appears exactly once in both `## Commits` and
  `## TDD Evidence`, that each row's `(Task, Commit)` pair matches a `## Commits` entry,
  that no `(Task, Commit)` pair appears twice, and that no row references a task the
  `task-list` still reports as `pending`.
- **validator-column-grammar**: The validator checks every cell against the inline grammar
  declared by the implementor prompt: `Layer ∈ {unit, integration, e2e, mixed, N/A}`;
  `RED == "written"`; `GREEN == "passed"`;
  `Triangulation ∈ {(N cases)|Single|N/A: reason}`;
  `Safety net ∈ {(passed: N/N)|N/A: new files|N/A: reason}`;
  `Refactor ∈ {clean|none needed|deferred}`. Off-grammar values are flagged with the
  severity listed in the severity-mapping capability.
- **validator-gate-classification**: The validator runs the required quality gates from
  the target repo's `CODING_STANDARDS.md` literally (ruff, pylint, pytest, etc., exactly
  as the standards declare, with conditional language respected). Gate failures on files
  listed in any row's `Non-test files` or `Test files` cells are CRITICAL (the row claims
  ownership); gate failures on files outside that union are WARNING (pre-existing /
  unrelated).
- **validator-audit-summary**: The validator appends `## TDD Evidence Audit` (placed
  AFTER `## Gates`) containing a `Check | Result | Details` table that summarises every
  TDD audit check, and mirrors every failed check into `## Findings` with its severity.
  `## Verdict` and archive routing continue to depend on `critical` from `## Verdict`.
- **severity-mapping-as-policy**: The mapping below is locked inline in the validator
  prompt and is the single source of truth:
  - **CRITICAL** — RED/GREEN cell off-grammar; Safety-net contradiction;
    `Test files == N/A` while `Non-test files` is non-empty (behavior change without
    tests); missing evidence row for a completed task; duplicate row; extra row;
    row references a Commit SHA not present in `## Commits`; task id not in
    `task-list`; gate failure on a row-owned file.
  - **WARNING** — `Refactor` cell empty/off-grammar; `Layer` cell outside the enum;
    gate failure on a file outside any row's column lists.
  - **pass-with-warnings** — verdict is permitted when only WARNING-severity TDD checks
    fail; `critical: 0`.
- **no-assertion-quality-audit**: The validator confirms the RED and GREEN cells contain
  the expected literal strings, not that the assertions inside those tests are
  well-formed. Scope explicitly excluded from v1.
- **backward-compat-legacy-suffix**: Any `## Commits` line carrying a trailing
  `; tests: <commands>` segment is accepted by the validator; only the prefix
  `- <sha> — task <id>: <summary>` is parsed.

## Approach

A resource-prompt contract change, end to end.

1. **Implementor prompt** (`change-implementor.md`): rewrite the TDD loop block so each
   task step writes (a) the canonical `## Commits` line and immediately below it (b) the
   matching `## TDD Evidence` row, both before advancing the loop. Inline the ten-column
   header and the per-column value grammar as literal text. Keep `## Remaining` and the
   result envelope untouched. Stay silent on skill loading.
2. **Validator prompt** (`change-validator.md`): keep `## Verdict`, `## Coverage`,
   `## Findings`, `## Gates` exactly as today. Append `## TDD Evidence Audit` AFTER
   `## Gates` with a `Check | Result | Details` summary table. Inline the textual
   cross-consistency checks, the column-grammar checks, and the severity mapping as
   policy authority. Inline the rule that the validator runs gates literally from
   `CODING_STANDARDS.md`, never inspects commit diffs, and never re-runs
   implementor-reported commands.
3. **No code module, no CLI, no new tests.** Audit logic lives in the validator prompt.
4. **Regression**: run `uv run pytest tests/test_renderers.py` and
   `uv run pytest tests/test_install.py` after the prompt edits to confirm envelope field
   labels (`partial:`, `changed_files:`, `remaining_tasks:`, `verdict:`, `critical:`) and
   shared envelope shape still pass.

The audit rules live inline as prose, not code. A self-checklist at the bottom of
`## TDD Evidence Audit` makes omissions visible in the validator's own output rather
than only at reviewer review.

## Affected Areas

- `src/ai_harness/resources/change-agent/change-implementor.md` — prompt body edit;
  frontmatter untouched.
- `src/ai_harness/resources/change-agent/change-validator.md` — prompt body edit;
  frontmatter untouched.
- `tests/test_renderers.py` — re-run as regression gate; no edits required.
- `tests/test_install.py` — re-run as regression gate; no edits required.

Explicitly NOT affected (left as a non-affected list so a careless review doesn't drift scope):

- `src/ai_harness/resources/change-agent/change-orchestrator.md` — orchestrator already
  injects TDD skill; no edit.
- `src/ai_harness/modules/harness/tdd_evidence.py` — does not exist and must not be
  created.
- `tests/test_tdd_evidence.py` — does not exist and must not be created.
- Any CLI surface or new subcommand.

## Risks

- **Backward compatibility** — `implementation.md` files from in-flight Changes predating
  this contract will fail the TDD audit by design. Mitigated by treating this Change as
  opt-in: only Changes started after merge are held to it.
- **Column grammar drift** — a future contributor adding a new `Refactor` value (e.g.
  `in-progress`) without updating both prompts produces a silently-WARNING or unexpectedly
  failing audit. Mitigated by making `change-implementor.md` the source of truth for
  grammar and `change-validator.md` reference it as authority.
- **Skill-injection boundary drift** — a future edit re-introducing skill-loading prose in
  `change-implementor.md` would duplicate the orchestrator's injection. Mitigated by an
  inline note in the validator prompt that the orchestrator owns skill injection and
  leaving the implementor prompt silent on the topic.
- **Pipe `|` inside Markdown cells** — a cell like
  `Non-test files: src/x.py | src/y.py` breaks table parsing. Mitigated by an explicit
  "no `|` inside cells" rule in the implementor template and a counted-cell-split
  CRITICAL in the validator.
- **Gate-failure ownership heuristic** — deciding whether a gate failure is
  "implementor-owned" is fuzzy. Mitigated by the simple rule: gate-failed file listed in
  any row's `Non-test files` or `Test files` → CRITICAL; otherwise → WARNING.
- **Severity policy creep** — a future contributor pushing `Refactor` to CRITICAL or
  relaxing a CRITICAL rule. Mitigated by inlining the severity mapping in
  `change-validator.md` so policy is one-prompt-local.
- **Audit rules live in prose** — a typo or omitted audit rule is only visible at audit
  time. Mitigated by a self-checklist at the bottom of `## TDD Evidence Audit` so a
  missed step shows up in the validator's own output.
- **Renderer-test coverage gap** — the existing renderer tests are tolerance-based on
  substring matches of envelope labels; they do not snapshot full prompt bodies. A
  deleted section would still pass. Mitigated by reviewing the diff of the two prompts
  in code review (out-of-loop) and by the self-checklist in the validator prompt.

## Rollback Plan

- Revert the two prompt files (`change-implementor.md`, `change-validator.md`) to their
  pre-Change versions. No Python module, CLI subcommand, or test file is added, so
  revert is a two-file commit.
- Validator behavior reverts to today's coverage-only verdict; in-flight Changes remain
  valid (their `implementation.md` files still satisfy the old contract).
- Existing renderer tests should pass unchanged after revert; if they don't, that
  indicates an unintended code/module edit slipped in and must be reverted separately.

## Dependencies

- The implementor must have access to `ai-harness task-list` and `ai-harness task-done`
  (existing CLI subcommands).
- The target repo must declare its required quality gates in `CODING_STANDARDS.md`; the
  validator runs them literally and respects conditional language there.
- The TDD skill is already injected by the change-orchestrator into the implementor
  prompt; this Change does not modify that and does not depend on it being modified.
- `tests/test_renderers.py` and `tests/test_install.py` must continue to pass after the
  prompt edits — they are the regression gate.

## Success Criteria

- `change-implementor.md` contains a `## TDD Evidence` table template whose header row is
  exactly: `Task | Commit | Non-test files | Test files | Layer | Safety net | RED |
  GREEN | Triangulation | Refactor`. Verified by direct read.
- `change-validator.md` contains a `## TDD Evidence Audit` section AFTER `## Gates`
  whose summary table header is exactly: `Check | Result | Details`. Verified by direct
  read.
- A Change that completed one task test-first produces `implementation.md` with one
  `## Commits` line and exactly one `## TDD Evidence` row whose `(Task, Commit)` pair
  matches the commit line, all cells off-grammar CRITICAL=0, and a `validation.md` whose
  `## TDD Evidence Audit` table shows `pass` for every check and whose `## Verdict` is
  `pass`.
- A Change that completes one task without writing tests produces `validation.md` with a
  CRITICAL row under `## Findings` (and its mirror in `## TDD Evidence Audit`) for
  "behavior without test", `critical: 1`, and an archive-blocking verdict.
- A Change that writes evidence rows for tasks `task-list` still reports as `pending`
  produces a CRITICAL "extra row" finding.
- A Change whose `Refactor` cells are blank produces `validation.md` with the
  `## TDD Evidence Audit` table showing WARN for Refactor and a WARNING under
  `## Findings`, with `critical: 0` and verdict `pass-with-warnings`.
- A Change whose `## Commits` lines still carry the legacy `; tests:` suffix parses
  cleanly: no CRITICAL finding, no spurious warnings, evidence rows still cross-match.
- `CODING_STANDARDS.md` gates are run literally, including conditional language; no gate
  command is hardcoded in either prompt.
- `uv run pytest tests/test_renderers.py` and `uv run pytest tests/test_install.py`
  remain green after the edits.
