# Archive Report: update-readme-after-refactor

## Summary

The `update-readme-after-refactor` SDD change has been archived from `openspec/changes/update-readme-after-refactor/` to `openspec/changes/archive/2026-06-16-update-readme-after-refactor/`. The verify verdict is `PASS WITH WARNINGS` — all 10 acceptance criteria and all cross-checks pass; the single pending task (4.1, readability review) is a soft human check that was addressed through in-chat correction rounds during the apply and verify phases. Net effect on the repo: three edits to `README.md` — the misleading `--json` claim corrected (`(it emits machine-readable JSON)`), `## What's in here` rewritten from an 11-row path-by-path table to a 5-bullet high-level description per the durable-docs principle, and `uv run pytest` added to `## Running tests`. Net line delta: 155 → 156 lines (1 line added net, with a post-verify correction that removed 11 table rows and added the 5-bullet structure plus closing sentence).

## Verdict

> Verdict line from verify-report.md: **PASS WITH WARNINGS**

PASS WITH WARNINGS

## Spec merge

Skipped — user explicitly skipped `sdd-spec` for this docs-only change, consistent with the previous `improve-readme-onboarding` change. The `proposal.md` served as the canonical spec. No `specs/` subdirectory was created in the change artifacts, and no canonical specs exist in `openspec/specs/` (the directory does not exist in this worktree). No canonical specs were created or modified.

## Artifacts archived

Five artifacts were moved. All live at the relative path `openspec/changes/archive/2026-06-16-update-readme-after-refactor/` inside the worktree:

- **`exploration.md`** — Pre-proposal audit of the README against PR #10's refactor (`artifacts/` and `commands/` packages). Confirmed the coordination risk was safe (the manifest does not enumerate the deleted sub-README), identified 6/9 sections as accurate, and recommended the three narrow edits that the proposal adopted.
- **`proposal.md`** — Canonical specification for the change: correct the `--json` claim, generalize the `src/ai_harness/` row, add `uv run pytest`. Defines the durable-docs principle and 4 primary acceptance criteria plus 5 re-verified previous criteria. Explicit out-of-scope boundaries documented.
- **`tasks.md`** — Twelve tasks across four phases (3 implementation, 8 verification, 1 review). Eleven checked complete; task 4.1 (readability review) remains unchecked by design — a soft human check superseded by multiple in-chat correction rounds during the apply and verify phases.
- **`apply-report.md`** — Full TDD-cycle documentation: RED-phase baselines (2 genuinely red: `--json` claim present, `uv run pytest` absent), GREEN-phase verification (all 10 checks passing POST-edit), and detailed deviation records documenting the post-verify user correction that rewrote `## What's in here`.
- **`verify-report.md`** — Independent verification confirming all 10 acceptance criteria and all cross-checks pass. Records the `PASS WITH WARNINGS` verdict, the out-of-band GitHub repo rename requirement, and the task-progress snapshot with task 4.1's intentional pending status.

## Files changed in the worktree (not yet committed)

Three edits to `README.md` (156 lines, currently uncommitted):

1. **`README.md` line 93 — `## Driving the SDD pipeline`**: Replaced `(use \`--json\` for machine-readable output)` with `(it emits machine-readable JSON)`. Rationale: `src/ai_harness/commands/sdd/status.py` hard-codes `json_output=True`; the `--json` Typer option is a no-op. The README now describes actual behavior.

2. **`README.md` `## What's in here` (~lines 115–125)**: Rewrote the section as a 5-bullet high-level description of the main tree regions (`src/ai_harness/`, `src/ai_harness/resources/`, `tests/`, `e2e/`, `openspec/`) plus a closing "For everything else, explore the tree." Removed the path-by-path table entirely. Canonical wording:

   ```
   - `src/ai_harness/` — the CLI package. Each `ai-harness` subcommand (`install`, `uninstall`, `sdd-status`, `sdd-continue`) is implemented in its own subpackage; per-CLI installers under `src/ai_harness/artifacts/installers/` decide which bundled resources get installed for which target harness.
   - `src/ai_harness/resources/` — the bundled artifacts (skills, prompts, agent configs, project config templates) that the installers copy into each AI harness's home directory. The CLI does NOT install this directory verbatim; the per-CLI installers enumerate the specific files they own.
   - `tests/` — Python unit tests for the CLI package. Run with `uv run pytest`.
   - `e2e/` — end-to-end test suite and Docker sandbox (`e2e/docker-test.sh`).
   - `openspec/` — spec-driven change artifacts for this project (`config.yaml`, `specs/`, `changes/`). The directory follows the OpenSpec spec format; the CLI implements the pipeline natively.

   The repo root also holds `pyproject.toml` (project metadata and dependencies) and `tasks.py` (Invoke tasks for running the e2e suite). For everything else, explore the tree.
   ```

3. **`README.md` `## Running tests` (~lines 129–133)**: Inserted a unit-test block before the e2e paragraph:

   ```
   Unit tests run against the Python source (no Docker needed):

   ```bash
   uv run pytest
   ```
   ```

Note: The worktree is NOT committed at archive time. The orchestrator will handle commit and PR after the user gives the go-ahead.

## Deviations preserved

Two deviation items were recorded in `apply-report.md`, carried over into this archive report:

1. **No deviations at apply time.** The initial apply matched the proposal and task list exactly. The prose for the `uv run pytest` lead-in uses "Unit tests run against the Python source (no Docker needed):" which is the phrasing specified in task 1.3.

2. **Post-verify user correction — `## What's in here` rewritten.** The user directed a rewrite from an 11-row path-by-path table into a 5-bullet high-level description with no table entries at all. The user clarified that the durable-docs principle applies more strictly than the original apply implemented: not even a single row should enumerate a subdirectory, even with a generic body. The correction was applied after the verify phase completed; all 10 acceptance criteria re-ran and passed after the rewrite. No regression on the previous change's criteria.

## Durable-docs principle — first canonical application

This change is the first README edit to explicitly apply the durable-docs principle end-to-end — not as a one-off, but as a documented rule that the apply and verify phases enforced. The principle states:

> The README points developers at stable regions (`src/ai_harness/`, `tests/`, `e2e/`) and stable commands (`uv run pytest`, `uv run inv test`, `e2e/docker-test.sh`, the `ai-harness` subcommands). It does not enumerate subpackages, modules, or test files. When a refactor changes the package layout, the README does not need to change; the developer explores the tree to find what changed.

The principle is recorded in the project's memory under topic key `preference/readme-durable-to-refactors` and is available for future README changes to consult.

## Warnings and out-of-band follow-up

1. **GitHub repo rename required.** The GitHub repository is still named `ai-harness-setup`. The README's clone command (`git clone https://github.com/diegoagd10/ai-harness.git`) will not work until the user renames the repo on GitHub. Suggested command for the user:

   ```bash
   gh repo rename ai-harness-setup ai-harness --repo diegoagd10/ai-harness-setup
   ```

   The user has acknowledged they will do this after archive. Do not run it as part of this change.

2. **Task 4.1 (readability review) remains pending by design.** The user addressed readability through in-chat correction rounds across both changes (`improve-readon-onboarding` and `update-readme-after-refactor`) rather than a separate subagent review. The latest readability pass was the user's "Esta perfecto ahora" approval after opening the worktree in Zed to visually review the post-correction README. Soft check, not blocking.

## Next

No further SDD phases. The orchestrator will now handle commit and PR (after the GitHub repo rename).
