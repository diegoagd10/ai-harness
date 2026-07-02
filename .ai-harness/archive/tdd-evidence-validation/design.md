# Design — tdd-evidence-validation

## Context

The change-agent loop runs implementor + validator on every file-backed Change. Today nothing forces the implementor to actually drive work test-first, and nothing in the validator proves the implementor followed it. Reviewers discover skipped TDD by reading diffs after the fact, by which point the opportunity to course-correct inside the loop is gone.

This Change tightens the loop with a **prompt/resource contract**: the implementor writes a structured `## TDD Evidence` table into `implementation.md` for every completed task commit, and the validator audits it through inline rules that gate archive routing.

v1 is two Markdown prompt resources — no Python audit module, no CLI subcommand, no assertion-quality audit, no git-SHA verification, no commit-diff inspection. The deep question is: where does the column grammar live, and which prompt owns which side of the cross-consistency contract, so the seam is small and the depth is large.

## Deep modules

### Implementor evidence writer (`change-implementor.md`)

- **Seam**: the `## TDD Evidence` table section in the rendered `implementation.md`. Every completed task commit appends exactly one row whose `(Task, Commit)` cells match the `## Commits` line just written. The row appears in `implementation.md` before the loop advances to the next task.
- **Interface** — exact column header, in this order:

  `Task | Commit | Non-test files | Test files | Layer | Safety net | RED | GREEN | Triangulation | Refactor`

  - Per-column value grammar (this prompt is the **source of truth** for both prompts):
    - `Task` — task id from `ai-harness task-list`.
    - `Commit` — full SHA from the commit just made.
    - `Non-test files` — comma-separated paths, no `|`, single line.
    - `Test files` — same shape; `N/A` allowed only when `Non-test files` is empty.
    - `Layer ∈ {unit, integration, e2e, mixed, N/A}`.
    - `Safety net ∈ {(passed: N/M where 0 ≤ N ≤ M)|N/A: new files|N/A: <reason>}`.
    - `RED == "written"` (literal).
    - `GREEN == "passed"` (literal).
    - `Triangulation ∈ {(N cases)|Single|N/A: <reason>}`.
    - `Refactor ∈ {clean, none needed}` (settled two-value contract — see Constraint 1).
  - No `|` inside any cell — forbidden because it breaks Markdown table parsing.
- **Hides**: how the implementor derives the cell values from the task, the test runs, the diff it just staged, and the commit it just made. The table just appears with the right cells; the implementor does all the bookkeeping.
- **Depth note**: one `## TDD Evidence` row per `task-done` + commit step — small fixed surface, long discipline contract. Deletion test: removing this section collapses the audit back to "verdict-only" and the loop loses the RED→GREEN tie to commits; the module earns its keep.

### Validator evidence auditor (`change-validator.md`)

- **Seam**: the `## TDD Evidence Audit` section in `validation.md`, placed **after** `## Gates`. Archive routing still keys off `verdict` / `critical` from `## Verdict`; every `fail` and every `warn` row in the audit table is mirrored into `## Findings` under the matching severity so existing routing is unchanged.
- **Interface** — exact audit summary header:

  `Check | Result | Details`

  - `Check` — short stable name from a fixed set:
    `section-present | cross-ref | no-duplicate | no-extra | grammar-red | grammar-green | safety-net | test-coverage | layer | refactor | gate-ownership | cell-count`.
  - `Result` — `pass` | `fail` | `warn`.
  - `Details` — one line: which row, which cell, which task id, which file path.
  - A self-checklist tail at the bottom of the section ticks off the audits the validator actually ran; a missing step is visible in the validator's own output rather than only at reviewer review.
- **Hides**: the parser (cell-count split, regex/equality against the column grammar, gate-failure ownership classifier). The auditor's contract is the `Check | Result | Details` table; the parser is internal and covered transitively.
- **Depth note**: one section, one summary table, a fixed set of check names, severity policy inlined once. Deletion test: removing this section reverts the validator to coverage-only verdict; everything the loop gained disappears, so the module earns its keep.

### Shared column grammar (cross-prompt constant)

- **Seam**: the implementor prompt inlines the grammar verbatim as the source of truth; the validator prompt re-declares the per-column regex/equality checks inline so the auditor can run them without re-reading the implementor prompt, and references the implementor prompt as the authority. The two prompt bodies never call each other at runtime; the contract is the table layout itself.
- **Hides**: nothing — this **is** the cross-prompt contract.
- **Depth note**: a real seam, not a naming accident. If either prompt diverges silently, the audit becomes over-strict (CRITICAL storm) or under-strict (silent WARNING). The risk is recorded below.

## Internal collaborators (not test seams)

- **Legacy `## Commits` suffix parser** (validator). Accepts `- <sha> — task <id>: <summary>` as the prefix; treats a trailing `; tests: <commands>` segment as harmless suffix noise. Hidden behind `cross-ref`; covered transitively when the audit reports a clean pass on a Change whose `## Commits` lines still carry the legacy suffix.
- **Cell-count splitter** (validator). Splits a row on `|` and verifies the count matches the ten-column header. Mismatch → CRITICAL under the `cell-count` check. Hidden; covered transitively by the same `cross-ref` and grammar rows.
- **Gate-failure ownership classifier** (validator). Walks the union of every row's `Non-test files ∪ Test files` columns; gate failure on a file in the union → CRITICAL under `gate-ownership`; outside the union → WARNING. Hidden; covered transitively by the `gate-ownership` row.
- **Self-checklist tail** (validator). A `## TDD Evidence Audit` tail that enumerates the check names; the validator ticks them off in its own output. Tested by the auditor's own output, not by an external test file.

## Seam map

```
                 writes
  implementor  ───────────────►  implementation.md
   (prompt)                       ├── ## Commits        (1 line per completed task)
                                  └── ## TDD Evidence   (1 row per completed task)
                                              │
                                              │ reads
                                              ▼
                 reads + audits     validation.md
  validator    ◄──────────────────  ├── ## Verdict / ## Coverage / ## Findings / ## Gates
   (prompt)                       └── ## TDD Evidence Audit   (Check | Result | Details)
                                              │
                                              │ mirrors fail / warn into
                                              ▼
                                       ## Findings  (CRITICAL | WARNING)
                                              │
                                              │ archive routing reads
                                              ▼
                                  verdict / critical  from  ## Verdict
```

The column grammar is the only cross-prompt dependency. It is declared in two places — the implementor prompt (full inline, source of truth) and the validator prompt (mirror with regex/equality re-declaration). Drift between the two prompt bodies is a known risk; both prompts reference each other as authority so future column additions are localized to the two files.

## Rejected alternatives

- **Python audit module under `src/ai_harness/modules/harness/tdd_evidence.py`** — rejected per PRD: scope creep. The audit logic stays in the validator prompt; the depth lives in prose, not code, and that is the v1 constraint, not a workaround. Tradeoff: prose audit is typo-prone; mitigated by the self-checklist tail.
- **`ai-harness validate-tdd` CLI subcommand** — rejected per PRD: scope creep. Archive routing already keys off `verdict` / `critical` from the existing envelope; a new subcommand would fork the routing path and require a separate invocation.
- **Per-subtask rows in the evidence table** — rejected per PRD: out of scope for v1. One row per top-level completed task commit. Subtask semantics are recoverable from the row's `Non-test files` / `Test files` cells if needed later.
- **Validator verifies commit SHAs exist in git history** — rejected per PRD: textual-only audit. The validator parses `## Commits`; it does not run `git rev-parse` against the SHA. Tradeoff: a hallucinated SHA passes; mitigated by the implementor being the one that just produced the commit and by the gate-failure ownership classifier catching most "did you actually commit it?" signals via the gate run.
- **Validator re-runs implementor-reported test commands verbatim** — rejected per PRD: the validator runs the gates declared in `CODING_STANDARDS.md` literally, with conditional language respected. Implementor-reported commands are advisory. Tradeoff: redundant runs disappear; mitigated by the standards file being the single source of truth and the validator not hardcoding any command.
- **Assertion-quality audit (RED/GREEN cell well-formed assertions inside the test)** — rejected per PRD: out of scope for v1. The auditor confirms the cells contain the expected literal strings, not that the assertions are well-formed.
- **Three-value `Refactor ∈ {clean, none needed, deferred}` (PRD as written)** — **rejected as a design contract**. The settled conversation before PRD allowed only `clean` or `none needed`; missing/malformed/off-grammar values are WARNING. This design honors the settled two-value contract. PRD drift is recorded as Constraint 1 below; PRD is not edited in this phase. Tradeoff: the implementor must write `clean` or `none needed` (or accept a `Refactor` WARNING); `deferred` is not a permitted value under v1.

## Constraints and risks

### Constraint 1 — settled `Refactor` contract is two-value, not three

The PRD as written declares `Refactor ∈ {clean, none needed, deferred}`. The settled conversation before PRD allowed only `clean` or `none needed`, with missing/malformed/off-grammar values as WARNING. The design treats the settled contract as authoritative: the implementor writes one of `{clean, none needed}` or accepts a `Refactor` WARNING; `deferred` and any other value are off-grammar WARNING. This is an explicit restriction to the settled values, **not** a silent expansion of the contract. PRD is not edited in this phase; the implementor and validator prompts implement the settled two-value form. If the PRD is later amended to add `deferred` (or any other value), this design is updated to mirror, and the validator prompt's severity mapping is reconsidered.

### Risk 1 — column grammar drift between the two prompts

A future contributor adding a new column value (e.g. `Refactor: in-progress`) in only one of the two prompts produces a silent WARNING storm or an unexpectedly failing audit. Mitigation: the validator prompt inlines the per-column grammar with the same regex/equality set the implementor prompt uses; both prompts reference each other as authority. Drift between the two prompt bodies is caught at audit time; the renderer test is a substring check, not a snapshot, so a deleted column would not fail the test. Out-of-loop code review of the diff is the secondary mitigation.

### Risk 2 — severity policy creep

A future contributor may push `Refactor` off-grammar from WARNING to CRITICAL or relax a CRITICAL rule. Mitigation: the severity mapping is locked inline in the validator prompt — not in a config file, not in a Python module. Any relaxation is a prompt diff and is reviewable.

### Risk 3 — backward compatibility for in-flight `implementation.md` files

A Change whose `implementation.md` predates this contract has no `## TDD Evidence` section. The validator reports CRITICAL `section-present` and archive is blocked. Mitigation: the Change is opt-in for future Changes; in-flight Changes complete with the old contract are not retroactively validated unless re-implemented.

### Risk 4 — pipe `|` inside Markdown cells

A cell like `Non-test files: src/x.py | src/y.py` breaks Markdown table parsing. Mitigation: the implementor template explicitly forbids `|` inside cells; the validator's parse step uses a counted split equal to the column count and surfaces CRITICAL under `cell-count` on mismatch.

### Risk 5 — skill-injection boundary drift

A future edit re-introducing TDD-skill-loading prose in `change-implementor.md` would duplicate the orchestrator's injection. Mitigation: the implementor prompt stays silent on skill loading; the validator prompt carries an inline note that the orchestrator owns skill injection and the implementor must not duplicate it.

### Risk 6 — gate-failure ownership heuristic is fuzzy

Whether a gate failure is "implementor-owned" is fuzzy. Mitigation: the classifier is the simple rule — gate-failed file in any row's `Non-test files ∪ Test files` → CRITICAL; outside the union → WARNING. Anything more elaborate (e.g. matching by directory, by git history) is out of scope for v1.

### Risk 7 — audit rules live in prose, not code

A typo or omitted audit rule surfaces only at audit time. Mitigation: the self-checklist tail in the `## TDD Evidence Audit` section enumerates the check names; the validator ticks them off in its own output, so a missing step is visible to the reviewer reading `validation.md` rather than only to a separate reviewer.

## Prompt budget (~100 LOC across the two prompts)

The new contract sections are budgeted at ~100 LOC across both prompts:

- **Implementor prompt additions** (~45 LOC): the `## TDD Evidence` table template in the `implementation.md` structure block; the per-column grammar inlined as a literal block; the loop instruction to append one matching row after every `task-done` + commit step; the no-`|` rule; the cross-reference to "this prompt is the grammar authority".
- **Validator prompt additions** (~55 LOC): the `## TDD Evidence Audit` section after `## Gates`; the `Check | Result | Details` summary table template; the fixed check-name list with severity per check; the `| inside cell` counted-split rule; the gate-ownership rule with the file-union classifier; the cross-reference to the implementor prompt as the grammar authority; the orchestrator-owns-skill-injection note; the self-checklist tail.

**Untouched**: `## Remaining` (implementor) and `## Verdict / ## Coverage / ## Findings / ## Gates` (validator). Frontmatter on both prompts. Result envelopes. `change-orchestrator.md`. `tests/test_renderers.py` and `tests/test_install.py` (run as regression gates, not edited). No Python module, no CLI subcommand, no new test file.
