# Exploration — human-review-gate

## Budget
70

## Affected Files
- docs/design/change-orchestrator.md — add explicit human review gate before implement; clarify routing/resume semantics.
- src/ai_harness/resources/change-agent/change-orchestrator.md — update orchestrator prompt to halt after tasks and wait for human confirmation.
- src/ai_harness/modules/harness/renderers.py — refresh change-orchestrator metadata/description if prompt semantics change.
- src/ai_harness/modules/harness/change.py — only if gate becomes a mechanical status token instead of prompt-only waiting.
- tests/test_renderers.py — lock rendered prompt/body contract so gate text cannot drift.

## Plan
- Decide whether gate is purely orchestrator-level waiting or needs persisted review state; prefer prompt-only unless resume correctness demands persistence.
- Insert a new review checkpoint after tasks complete and before change-implementor launches.
- Keep CLI status derivation mechanical unless a durable gate marker is required.
- Add/adjust tests around rendered prompt contract and any new routing/state token.

## Edge Cases
- Resume after compaction/session gap: gate may need to reappear if no durable approval marker exists.
- Tasks/specs/design change after review request: gate must re-open for the updated artifacts.
- Existing blockers (missing prd/design/specs/tasks) should still block before review, not be hidden by the new gate.
- Large-change split path must not accidentally demand implementation review on parent decomposition manifests.

## Test Surface
- renderers test for change-orchestrator body/metadata parity.
- change status test only if routing state gets a new review token or waiting reason.
- manual smoke: run change flow through tasks completion and confirm implementor is not spawned until human says continue.

## Risks
- Prompt-only gate can drift or be bypassed if the orchestrator text is not kept in sync; mitigate with explicit prompt wording and render tests.
- No durable approval marker means repeated review prompts on resume; mitigate by deciding whether the gate is session-only or persisted.
- Adding a new mechanical token expands the status contract and may ripple into CLI/tests; avoid unless durability is truly needed.
