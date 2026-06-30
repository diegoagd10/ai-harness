# Exploration — whole-repo-cleanup-review

## Budget
80

## Affected Files
- docs/design/change-orchestrator.md — move into `.ai-harness/changes/archive/borrow-gentle-orchestrator/` so durable design lives with archived change history.
- .ai-harness/changes/archive/borrow-gentle-orchestrator/ — archive target already holds PRD/spec/validation trail; absorb design doc there.
- docs/adr/0011-planning-entry-agent-and-size-routing.md — safe delete candidate; superseded by `docs/design/change-orchestrator.md`.
- docs/adr/0008-worktree-current-branch-and-delete.md — keep active; still referenced by 0009 and part of the numbering collision.
- docs/adr/0008-copilot-loop-agents-native-model.md — keep active; README still cites it for Copilot model behavior.
- docs/adr/0012-file-backed-changes-disk-state-machine.md — keep active; change filesystem state machine still load-bearing for 0014.
- docs/adr/0013-change-orchestrator-worktree-branch-pr-agnostic.md — keep active; documents the no-`main` guard still relied on by change docs.
- docs/adr/0014-change-orchestrator-deep-modules.md — keep active; depends on 0012 and defines the deep-module seam.

## Plan
- Move `docs/design/change-orchestrator.md` into the archive change folder first; that doc is durable narrative, not active runtime prompt source.
- Delete `docs/adr/0011-planning-entry-agent-and-size-routing.md`; it is superseded and no longer needed as an active ADR.
- Leave the 0008 collision alone for now; both 0008 ADRs still have live references, so renumbering/deletion needs separate confirmation.
- Re-grep active docs after the move/delete to ensure no accidental references to the removed ADR remain.

## Edge Cases
- 0008 collision is still naming-only: `README.md` cites the Copilot 0008, while 0008 worktree ADR remains separately referenced by 0009.
- `src/ai_harness/resources/change-agent/change-orchestrator.md` stays load-bearing product source; only `docs/design/change-orchestrator.md` moves.
- Archived borrow-gentle-orchestrator docs already cite the design doc as evidence, so moving it should preserve archive cohesion.
- Deleting 0011 without a follow-up grep could leave stale rationale links in adjacent docs or notes.

## Test Surface
- Grep for `ADR 0011` and `0011-planning-entry-agent-and-size-routing` after delete.
- Grep for `docs/design/change-orchestrator.md` to confirm only intended archive/history references remain after the move.
- Grep for `0008-worktree-current-branch-and-delete` and `0008-copilot-loop-agents-native-model` to preserve known collision context.
- Verify `docs/adr/0012-file-backed-changes-disk-state-machine.md`, `0013`, and `0014` still have valid downstream references.

## Risks
- False positive: 0011 may still be useful as a historical artifact if any future audit wants the old planning rationale.
- Moving the design doc without updating archive citations can leave stale paths, even if the content is preserved.
- Treating 0008 collision as cleanup can break active docs; renumbering needs separate, evidence-backed follow-up.
