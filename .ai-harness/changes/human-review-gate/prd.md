# PRD — human-review-gate

## Intent

Add a human-in-the-loop review checkpoint to the change-orchestrator so implementation cannot start immediately after planning artifacts are produced. The user must get an explicit opportunity to review the PRD, design, specs, and tasks before the orchestrator launches `change-implementor`.

## Scope

### In

- Add an explicit review/wait checkpoint after tasks are complete and before implementation begins.
- Prefer a prompt-level `waiting` gate in the change-orchestrator instructions.
- Update change-orchestrator documentation so the artifact flow and resume semantics describe the human review gate.
- Add render-level tests that lock the gate wording and reduce prompt drift risk.
- Consider status/schema changes only if durable resume behavior requires a persisted approval marker.

### Out

- Implementing a full approval UI or separate review command.
- Publishing GitHub issues, PRDs, or external tracker artifacts.
- Changing product implementation flow beyond the orchestrator gate.
- Adding new status schema tokens unless prompt-level waiting cannot satisfy resume expectations.
- Reworking parent large-change decomposition behavior except to ensure it is not accidentally gated as implementation.

## Capabilities

- Review checkpoint before implementation: change-orchestrator stops after PRD/design/specs/tasks are ready and asks the human to review before launching implementation.
- Approval-controlled continuation: implementation begins only after the human explicitly confirms continuation.
- Resume-safe review behavior: on resume, the orchestrator either re-presents the review checkpoint or honors a durable approval marker if persistence is introduced.
- Artifact-change invalidation: if PRD, design, specs, or tasks change after a review request, the gate reopens before implementation.
- Prompt contract coverage: tests assert rendered change-orchestrator content includes the review gate and cannot silently drift.
- Documentation alignment: design docs explain the review gate, routing order, and when mechanical status changes are or are not used.

## Approach

Use the lightest viable gate first: update the change-orchestrator prompt to enter a `waiting` state after tasks are complete and before invoking `change-implementor`. The gate should name the artifacts to review and require explicit human confirmation before proceeding.

Keep CLI/status behavior mechanical unless resume durability proves insufficient. If the prompt-only gate creates unacceptable repeated prompts or cannot distinguish approved-from-unapproved resumes, add a narrow persisted approval marker or waiting reason and update the status contract accordingly.

Treat the gate as part of the planning-to-implementation seam, not as a product-code implementation detail. Existing blockers for missing PRD, design, specs, or tasks should remain earlier than the review gate, so the review request only appears when reviewable artifacts exist.

## Affected Areas

- `docs/design/change-orchestrator.md` — document the human review gate and clarify routing/resume semantics.
- `src/ai_harness/resources/change-agent/change-orchestrator.md` — update orchestrator instructions to wait for human confirmation before implementation.
- `src/ai_harness/modules/harness/renderers.py` — refresh rendered change-orchestrator metadata/description if prompt semantics require it.
- `src/ai_harness/modules/harness/change.py` — touch only if durable gate state or a new mechanical status token is required.
- `tests/test_renderers.py` — add/adjust render contract coverage for gate wording and metadata/body parity.

## Risks

- Prompt drift may weaken or bypass the gate if the orchestrator wording changes without test coverage.
- Prompt-only gating may repeatedly request review after resume if there is no persisted approval marker.
- Adding a new status token or schema field can ripple through CLI output, tests, and change status logic.
- If artifacts change after review, stale approval could let implementation proceed against unreviewed content.
- Parent large-change decomposition flows could be incorrectly blocked by an implementation gate intended for executable child changes.

## Rollback Plan

Revert the orchestrator prompt/documentation changes and any render tests that assert the gate. If a persisted status token or approval marker is added, remove it with a compatibility-safe fallback so existing changes return to the previous tasks-to-implementation path.

## Dependencies

- Existing change-orchestrator flow and prompt rendering pipeline.
- Existing PRD, design, specs, and tasks artifact lifecycle.
- Existing renderer tests for prompt/body contract coverage.
- Decision on whether resume durability needs persisted approval state.

## Success Criteria

- When PRD, design, specs, and tasks are complete, change-orchestrator stops and asks for human review instead of launching `change-implementor`.
- Implementation only starts after explicit human confirmation.
- Existing missing-artifact blockers still fire before the review gate.
- Resume behavior is intentional: either repeat the review request safely or honor persisted approval if implemented.
- Render tests fail if the human review gate wording disappears from the orchestrator prompt.
- Documentation matches the implemented routing and resume behavior.
