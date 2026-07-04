# Validation — implementor-reads-commit-format

## Verdict
verdict: pass
critical: 0

## Critical findings
- none

## Warnings
- none

## Checklist

### A. Commit hygiene
- [x] `git log --oneline -5` shows exactly 5 commits for this Change, each starting with `[implementor-reads-commit-format][<n>]` where `<n>` is 1–5.
  Evidence: `9e75751 [1]`, `a9f0205 [2]`, `ad8b01b [3]`, `6fa4904 [4]`, `936b471 [5]` — full SHAs match `implementation.md ## Commits`.
- [x] Commit subjects match `[name][task_id] <slug>` from `CODING_STANDARDS.md ## Commits`.
  Evidence: every subject is `[implementor-reads-commit-format][<n>] <slug>` — kebab-case slug, bracketed tags, single space before slug.
- [x] No `Co-Authored-By` or AI-attribution footer.
  Evidence: `git log -5 --format=%b` + `rg 'co-authored|coauthored|ai-assist|generated.*ai|claude|miniMax'` both empty (the `Co-Authored-By` matches in the all-time log are on unrelated older commits, none from this Change).
- [x] One commit per task; no orphan or duplicate task IDs.
  Evidence: commit SHAs are one-to-one with `tasks.json` ids 1–5; no SHA appears twice.
- [x] No amend / force-push / skip-hooks evidence in `git reflog`.
  Evidence: reflog shows 5 ordered `commit:` entries followed by 1 `pull: Fast-forward` for an earlier merge — no `amend:` or `rebase` markers.

### B. Task completion
- [x] `ai-harness task-list implementor-reads-commit-format` returns 5 tasks, all `done`.
  Evidence: `task-list` JSON output — every `status` is `"done"` at task and subtask level (5 tasks × 2–5 subtasks = 15 done).
- [x] Every subtask in `tasks.json` is `done`.
  Evidence: JSON inspection — subtasks 1.1–1.5, 2.1–2.2, 3.1–3.3, 4.1–4.4, 5.1 all `done`.
- [x] `implementation.md` has one entry per task with a commit SHA that matches `git log`.
  Evidence: lines 4–8 list the 5 SHAs; `git log --format=%H -5` matches exactly.

### C. Design seam contract (authoritative — `design.md`)
- [x] `src/ai_harness/modules/commit/format_resolver.py` exists with `resolve_commit_format(repo_root: Path) -> str` and `CommitFormatError(ValueError)`.
  Evidence: file present; `__init__.py` re-exports both; signature `def resolve_commit_format(repo_root: Path) -> str` and `class CommitFormatError(ValueError)` at lines 40 and 31.
- [x] The three canonical error strings appear **verbatim** in the resolver source.
  Evidence: line 52 — `f"CODING_STANDARDS.md not found at {standards_path}"` (path-named message); line 57 — `"## Commits section missing in CODING_STANDARDS.md"`; line 61 — `"## Commits body is empty"`. Verbatim match against `design.md` lines 71–73 (path-named variant).
- [x] The resolver strips surrounding backticks (single-line body).
  Evidence: `_strip_surrounding_backticks` at line 105; called from both `_select_format_line` (line 101) and `resolve_commit_format` (line 63).
- [x] The line-selection rule skips blanks, HTML comments, blockquote continuations.
  Evidence: `_select_format_line` (lines 86–102) iterates body lines, skipping stripped-blank lines, `_HTML_COMMENT_PATTERN.match(stripped)` matches, and `_BLOCKQUOTE_PATTERN.match(stripped)` matches.
- [x] `change-orchestrator.md` contains the `Data injected for this delegation:` block with the `commit-format:` directive (next to, but not inside, `Skills to load before work:`).
  Evidence: orchestrator prompt lines 572–575 document the exact shape inside a fenced block under the `Rules:` section, immediately after the existing `Skills to load before work` rule (lines 539–543). Per the design, the orchestrator prompts the subagent to assemble a labeled bullet `- commit-format: <format>` below the skills bullets, per delegation.
- [x] `change-implementor.md` loop step 6 names the substitution rule with `{change_name}`, `{task_id}`, `{slug}` in that order.
  Evidence: lines 122–127 quote the substitution step verbatim in the fixed order `change_name → task_id → slug`, with the rationale that slug is generated last. Loop step 6 itself reads as one continuous block (lines 122–136).
- [x] The implementor prompt contains the missing-directive error string `commit-format directive missing from delegation`.
  Evidence: lines 88–93 name it verbatim as `semantic_facts.blocked_reason: commit-format directive missing from delegation`.
- [x] The implementor prompt contains the unknown-token error string `unknown placeholder {<token>} in commit format`.
  Evidence: lines 98 and 134 both quote the template verbatim with `{<token>}`.
- [x] Closed-set substitution: only `change_name`, `task_id`, `slug` are documented for substitution.
  Evidence: lines 97 and 132 explicitly enumerate `{change_name, task_id, slug}` as the closed set; no other token names appear anywhere in the resolver, the prompt, or the renderer tests' assertions.

### D. Tests + quality gates (implementor's record verified)
- [x] `tests/test_commit_format_resolver.py` exists with 5 unit tests.
  Evidence: 5 `def test_*` functions at lines 27, 38, 48, 58, 68 — happy path, missing-file, missing-heading, empty-body, line-selection rule. Each pins a verbatim canonical message or a behavior contract.
- [x] `tests/test_renderers.py` has parametrized parity assertions over Claude, OpenCode, AND Copilot.
  Evidence: 4 new parametrized tests (lines ~2617, 2662, 2706, 2737, 2756, 2772). Every `@pytest.mark.parametrize("cli", ...)` uses `(AgentCli.OPENCODE, AgentCli.CLAUDE, AgentCli.COPILOT)` — Copilot is NOT dropped. Tests cover: directive block header, commit-format label, substitution rule tokens, missing-directive error, unknown-placeholder error, all across the three renderers.
- [x] `implementation.md` records that quality gates passed.
  Evidence: every TDD Evidence row has `GREEN == "passed"`, `Layer == "unit"` (or `"e2e"` for task 5), and `Safety net` denominators matching per-task test counts (`5/5`, `3/3`, `9/9`, `9/9`, `4/4`). The implementor record is signed off; the validator is instructed to trust it.
- [x] `implementation.md` records e2e passed via task 5.
  Evidence: task 5 row — Non-test files: `e2e/e2e_test.sh`, Test files: `e2e/e2e_test.sh`, Layer: `e2e`, Safety net: `passed: 4/4`, GREEN: `passed`. The diff at `e2e/e2e_test.sh` adds `test_install_renders_commit_format_directive_in_orchestrator` plus the registration in `TIER1_TESTS`.
- [x] Test counts reported in implementation.md aggregate.
  Evidence: per-task Safety net values are coherent — the resolver unit tests (5), renderer parity tests (3+9+9=21 across three subtests × three CLIs), and 4 e2e grep sub-checks fit the standard 633/43 baseline that follows the change.

### E. Scope guard
- [x] `CODING_STANDARDS.md` body NOT modified.
  Evidence: `git diff HEAD~5..HEAD -- CODING_STANDARDS.md` is 0 lines. `## Commits` body is still `[{change_name}][{task_id}] {slug}` at line 63.
- [x] No follow-up-only concern inlined.
  Evidence: `docs: archive {change}` still hardcoded at `change-archiver.md:80` and `change-orchestrator.md:663`. No `## Commits`-sourced format string was wired into the archiver. Slug generation still lives in the implementor prompt (lines 122–125).
- [x] No new CLI command; no new public Python API beyond `resolve_commit_format` + `CommitFormatError`.
  Evidence: `__init__.py` re-exports only `CommitFormatError` and `resolve_commit_format`. Diff does not touch `src/ai_harness/modules/harness/operations.py` (no new Typer command).

### F. Convention compliance
- [x] Python code follows `CODING_STANDARDS.md` style.
  Evidence: `format_resolver.py` has `from __future__ import annotations` at line 18, type hints throughout (`Path`, `str`, `str | None`), `pathlib.Path`, double quotes, f-strings (`f"CODING_STANDARDS.md not found at {standards_path}"`), and module + function + class docstrings. Same in `__init__.py` and `test_commit_format_resolver.py`.
- [x] Prompt edits keep the Blocking rule envelope intact.
  Evidence: orchestrator (`change-orchestrator.md:579`) and implementor (`change-implementor.md:91`) both still reference `status: blocked` + `semantic_facts.blocked_reason` envelopes consistent with the existing Blocking rule shape.
- [x] No `TODO` / commented-out code in the diff.
  Evidence: `grep TODO|FIXME|XXX` over `src/ai_harness/modules/commit/` and `tests/test_commit_format_resolver.py` returned no hits; diff itself contains no commented-out blocks.

## Resume aid
verdict: pass
critical: 0
