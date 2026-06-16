# Archive Report: improve-readme-onboarding

## Summary

The `improve-readme-onboarding` SDD change has been archived from `openspec/changes/improve-readme-onboarding/` to `openspec/changes/archive/2026-06-16-improve-readme-onboarding/`. The verify verdict is `PASS WITH WARNINGS` — all five acceptance criteria and both cross-checks pass; the single pending task (4.1, readability review) is a soft human check that was addressed through multiple in-chat correction rounds during the apply phase. Net effect on the repo: `README.md` rewritten (155 lines, new section structure), `src/ai_harness/resources/agent-clis/opencode/README.md` deleted (59 lines), net -7 lines across the worktree.

## Verdict

> Verdict line from verify-report.md: **PASS WITH WARNINGS**

PASS WITH WARNINGS

## Spec merge

Skipped — user explicitly skipped `sdd-spec` for this docs-only change; the `proposal.md` served as the canonical spec. No `specs/` subdirectory was created in the change artifacts, and no canonical specs exist in `openspec/specs/` (the directory does not exist). No canonical specs were created or modified.

## Artifacts archived

Five artifacts were moved. All live at the relative path `openspec/changes/archive/2026-06-16-improve-readme-onboarding/` inside the worktree:

- **`exploration.md`** — Pre-proposal audit of the existing README: broken install paths (`cd cli`, `make install`), missing problem statement, stale `prompts/commands/` references. Recommended the section order that the proposal largely adopted.
- **`proposal.md`** — Canonical specification for the change: defines the new seven-section README structure, the sub-README deletion, the acceptance criteria (5 binary checks), explicit out-of-scope boundaries, and the merge-conflict mitigation note with the `refactor-commands-install-uninstall` branch.
- **`tasks.md`** — Ten tasks across three phases (4 implementation, 5 verification, 1 review). Nine checked complete; task 4.1 (readability review) remains unchecked by design — a soft human check superseded by three rounds of user corrections during the apply phase.
- **`apply-report.md`** — Full TDD-cycle documentation: RED-phase baselines (all 5 criteria failing pre-edit), GREEN-phase verification (all 5 passing POST-edit plus cross-checks), and detailed deviation records documenting six corrections the user directed during the apply walkthrough (section rename, repo-vs-binary distinction, project-wide rename, SSH→HTTPS switch, SSH-note removal, net line delta).
- **`verify-report.md`** — Independent verification confirming all five acceptance criteria and both cross-checks pass. Records the `PASS WITH WARNINGS` verdict, the out-of-band GitHub repo rename requirement, and the task-progress snapshot with task 4.1's intentional pending status.

## Files changed in the worktree (not yet committed)

- **`README.md`** — Rewritten (155 lines). New section structure: `# ai-harness`, `## Why we built this`, `## What this tool does` (with SDD-pipeline ASCII diagram migrated verbatim from the sub-README), `## Getting started` (corrected `uv tool install .` install path, HTTPS clone URL), `## Driving the SDD pipeline` (corrected section — replaced misleading `openspec init --tools opencode` with native `sdd-status`/`sdd-continue` subcommands, added Engram prerequisite), `## What's in here` (directory table with `{{HOME}}` explanation), `## Running tests`, `## Contributing`.
- **`src/ai_harness/resources/agent-clis/opencode/README.md`** — Deleted (59 lines). Content migrated to `## What this tool does` (SDD diagram) and `## What's in here` (`{{HOME}}` explanation under the `agent-clis/opencode/` table row). Confirmed safe: `main.py` sources only `opencode.json` from that directory, not the README.

Note: The worktree is NOT committed at archive time. The orchestrator will handle commit and PR after the user gives the go-ahead.

## Deviations preserved

Six deviations from the original proposal were recorded in `apply-report.md`. Each is preserved here for traceability:

1. **"See also" section omitted** — The proposal listed 9 sections but marked "See also" as omitted. Followed the proposal (the canonical spec). No action required.
2. **Seven `##` headings (>= 5 required)** — The new README has 7 `##` headings; the acceptance criterion requires >= 5, and all five required headings are individually verified present. The extra two (`## Driving the SDD pipeline` and `## What's in here`) are correct and intentional. No action required.
3. **User correction: replaced "Using the OpenSpec template" with "Driving the SDD pipeline"** — The user identified the original section was misleading. Corrected to describe the native `ai-harness` subcommands (`sdd-status`, `sdd-continue`), added the Engram prerequisite, removed the incorrect `openspec init --tools opencode` command, and updated related table rows in `## What's in here`. No action required.
4. **User follow-up: repo-vs-binary distinction added and then removed** — Added an explicit "this repo is `ai-harness-setup`; the tool is `ai-harness`" sentence to prevent naming confusion, then removed it when the user clarified the entire project should be renamed to `ai-harness` (making the distinction redundant). No action required.
5. **Project rename: `ai-harness-setup` → `ai-harness`** — H1, bolded mentions, clone URL, and issues URL all updated. The README is now internally consistent. **Out-of-band action:** the GitHub repo must be renamed from `ai-harness-setup` to `ai-harness` for the clone command to work.
6. **SSH → HTTPS for canonical clone URL; SSH variant removed** — Updated `## Getting started` to use HTTPS as the primary clone URL. Removed the secondary SSH note after the user identified it as patronizing noise. No action required.

## Warnings and out-of-band follow-up

1. **GitHub repo rename required.** The GitHub repository is still named `ai-harness-setup`. The README's clone command (`git clone https://github.com/diegoagd10/ai-harness.git`) will not work until the user renames the repo on GitHub. Suggested command for the user:

   ```bash
   gh repo rename ai-harness-setup ai-harness --repo diegoagd10/ai-harness-setup
   ```

   The user has acknowledged they will do this after archive. This is not an SDD concern; it is a remote-GitHub state action.

2. **Task 4.1 (readability review) remains pending by design.** The user addressed readability through multiple in-chat correction rounds during the apply phase rather than via a separate subagent review. The verification report lists it as unchecked with the explicit note: "Task 4.1 remains unchecked by design — it is the human soft-check readability review." Soft check, not blocking.

## Next

No further SDD phases. The orchestrator will now handle commit and PR (after the GitHub repo rename).
