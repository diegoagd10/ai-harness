# PRD — whole-repo-cleanup-review

## Intent

Reduce repository clutter and shrink the surface area future explorer runs have to
reason over by relocating durable design narrative into the change archive that
owns it and removing a superseded ADR. This is a **docs/ADR-only cleanup** — no
product code, no runtime prompts, no skill changes.

## Scope

### In

- Move `docs/design/change-orchestrator.md` into
  `.ai-harness/changes/archive/borrow-gentle-orchestrator/` so durable design
  travels with the change history it belongs to.
- Delete `docs/adr/0011-planning-entry-agent-and-size-routing.md` because it is
  superseded by later ADRs and no longer load-bearing for any active doc.
- Re-grep the active doc tree after the move/delete to confirm no stale
  references to the moved or removed paths remain.

### Out

- `.agents/skills/**` and `.claude/skills/**` — MUST NOT be touched. Skills are
  the runtime contract and are preserved verbatim.
- The ADR `0008` numbering collision (two ADRs share number `0008`) — out of
  scope. Both 0008s have live references; resolving the collision needs a
  separate, evidence-backed follow-up Change.
- `src/ai_harness/resources/change-agent/change-orchestrator.md` — out of scope.
  This is a load-bearing runtime prompt shipped via the package resources
  system. KEEP as-is.
- Any product code, tests, build config, or dependency changes.
- Renumbering of remaining ADRs.
- Edits to active ADRs `0008-worktree-current-branch-and-delete.md`,
  `0008-copilot-loop-agents-native-model.md`, `0012`, `0013`, or `0014`.

## Capabilities

- **archive-design-doc**: relocate the design narrative for the borrow-gentle-orchestrator change into its own archive folder.
  - The system MUST move `docs/design/change-orchestrator.md` to
    `.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
    preserving the file's bytes verbatim (no content edits during the move).
  - The system MUST NOT leave a copy of the file at
    `docs/design/change-orchestrator.md` after the move.
  - The system SHOULD update any cross-reference inside the
    `borrow-gentle-orchestrator/` archive (e.g. `exploration.md`,
    `validation.md`) that links to the old `docs/design/change-orchestrator.md`
    path so the archive stays self-consistent.
  - Acceptance: a `change-validator` run post-archive MUST confirm
    `docs/design/change-orchestrator.md` no longer exists and the file is
    present at the archive target.

- **delete-superseded-adr**: remove ADR 0011 because its planning rationale is
  captured by later ADRs and the design doc.
  - The system MUST delete
    `docs/adr/0011-planning-entry-agent-and-size-routing.md`.
  - The system MUST NOT delete or rename any other ADR in `docs/adr/`.
  - Acceptance: a `change-validator` run post-archive MUST confirm the file is
    absent and the remaining ADRs `0008-worktree-current-branch-and-delete.md`,
    `0008-copilot-loop-agents-native-model.md`, `0012`, `0013`, and `0014` are
    still present and unchanged.

- **preserve-skills-and-runtime-prompt**: keep the protected paths untouched.
  - The system MUST NOT modify any file under `.agents/skills/**` or
    `.claude/skills/**`.
  - The system MUST NOT modify
    `src/ai_harness/resources/change-agent/change-orchestrator.md`.
  - Acceptance: a `change-validator` run post-archive MUST confirm the set of
    files under those three paths equals the pre-archive snapshot (byte-for-byte
    on the runtime prompt; presence-only on the skill trees).

- **no-stale-references**: ensure no active doc still cites the moved or deleted
  paths after the operation.
  - The system MUST grep the repository (excluding `.git/`, archived changes,
    and the moved file itself at its new location) for:
    - `docs/design/change-orchestrator.md`
    - `0011-planning-entry-agent-and-size-routing`
    - `ADR 0011`
  - The system SHOULD update or remove any remaining hit so the repo does not
    ship broken links.
  - Acceptance: a `change-validator` run post-archive MUST report zero hits for
    the patterns above outside the archive's own historical notes and the
    PR/issue metadata that pre-date this change.

- **preserve-0008-collision-context**: keep the known `0008` collision as-is.
  - The system MUST NOT rename, renumber, delete, or otherwise alter either
    `docs/adr/0008-worktree-current-branch-and-delete.md` or
    `docs/adr/0008-copilot-loop-agents-native-model.md`.
  - The system SHOULD leave a one-line note in this PRD's Risks section
    (already done below) flagging the collision as a deferred follow-up.
  - Acceptance: a `change-validator` run post-archive MUST confirm both 0008
    files are byte-identical to the pre-archive snapshot.

## Approach

Single small-change implementation, executed after a human review gate:

1. Open a worktree on a feature branch.
2. `git mv docs/design/change-orchestrator.md
   .ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
   so history follows the file.
3. `git rm docs/adr/0011-planning-entry-agent-and-size-routing.md`.
4. Run the reference greps listed in the `no-stale-references` capability and
   patch any active-doc hit (archive-internal references are left alone).
5. Run `change-validator` to confirm every acceptance criterion above.
6. Hand off to a human reviewer for the explicit review gate; only then
   archive the change folder per the standard file-backed Change lifecycle.

No new seams, no new modules, no schema changes. The change is purely a
relocation plus one deletion.

## Affected Areas

- `docs/design/` — loses one file (moves out).
- `docs/adr/` — loses ADR `0011`.
- `.ai-harness/changes/archive/borrow-gentle-orchestrator/` — gains the design
  doc and possibly a one-line path fix in its own notes.
- Any active doc or ADR that referenced the moved design doc or ADR `0011` —
  limited, surgical edits only to update paths or drop stale links.

## Risks

- **Stale paths in archive notes.** The `borrow-gentle-orchestrator` archive
  cites the design doc by its old path. Mitigated by the `archive-design-doc`
  capability's SHOULD clause to update cross-references inside the archive.
- **Stale links in active docs.** Removing ADR 0011 or moving the design doc
  may leave broken links in surviving ADRs or `docs/`. Mitigated by the
  `no-stale-references` capability and its acceptance criterion.
- **Historical audit loss.** ADR 0011 may still be useful as a historical
  artifact. Mitigated by git history (the file is committed history, not
  truly gone) and by the `supersedes` relationship to later ADRs being
  captured in the change's commit message.
- **0008 collision deferred.** Both 0008 ADRs remain live and ambiguously
  numbered. Not addressed in this change; tracked here as a known follow-up.
  Do not bundle the resolution into this cleanup.

## Rollback Plan

- `git revert` the cleanup commit. Both the move and the delete are committed
  as a single change, so a single revert restores the prior tree.
- If the cleanup commit has already been archived, restore the moved file from
  the archive target back to `docs/design/` and re-add ADR 0011 from the
  pre-archive git ref. No data loss either way: git history retains both the
  old and new locations of the design doc and the prior contents of ADR 0011.

## Dependencies

- `git` for `git mv` / `git rm` so history follows the file.
- The `change-validator` workflow to run the post-archive acceptance checks.
- A human reviewer to fire the explicit review gate before the change is
  archived (this gate is non-optional — see Success Criteria).

## Success Criteria

- `docs/design/change-orchestrator.md` no longer exists at its old path; the
  file is present at
  `.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
  with identical bytes.
- `docs/adr/0011-planning-entry-agent-and-size-routing.md` is deleted; no
  other ADR was modified.
- `.agents/skills/**`, `.claude/skills/**`, and
  `src/ai_harness/resources/change-agent/change-orchestrator.md` are
  byte-identical to the pre-archive snapshot.
- The `no-stale-references` grep returns zero hits for the three target
  patterns outside the archive's own historical notes.
- `change-validator` reports green on every acceptance criterion in the
  Capabilities section.
- A human reviewer has explicitly approved the change before it is archived
  (the **human review gate**). The loop MUST NOT archive without that
  approval.
