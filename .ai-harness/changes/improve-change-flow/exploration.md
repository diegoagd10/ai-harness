# Exploration — improve-change-flow

## Budget
610

## Affected Files
- src/ai_harness/modules/harness/change.py — replace the single global first-missing-phase derivation with slice-aware routing and retain terminal archive preconditions.
- src/ai_harness/modules/harness/tasks.py — expose the minimum slice/task association and completion query needed by routing, without introducing the deferred task-ledger/DAG model.
- src/ai_harness/resources/change-agent/change-orchestrator.md — instruct the coordinator to plan, review, implement, and validate one capability slice before requesting later slices; retain an explicit escalation/review gate for high-risk work.
- src/ai_harness/resources/change-agent/change-propose.md — require independently deliverable, ordered capabilities and an initial thin-slice recommendation.
- src/ai_harness/resources/change-agent/change-design.md — make design optional and scoped to a capability unless cross-cutting risk requires a change-wide design.
- src/ai_harness/resources/change-agent/change-specs.md — create or extend exactly the currently selected capability spec rather than requiring every PRD capability before implementation.
- src/ai_harness/resources/change-agent/change-tasks.md — create tasks only for the selected capability and preserve the existing task CLI as the persistence owner.
- src/ai_harness/resources/change-agent/change-implementor.md — implement the selected ready slice, return to planning when more PRD capabilities remain, and retain per-task commits/TDD evidence.
- src/ai_harness/resources/change-agent/change-validator.md — validate each delivered slice and distinguish slice feedback from final change validation/archive readiness.
- expected/change-*.md — update rendered-resource fixtures for every changed prompt resource.
- tests/test_change.py — cover slice-aware recommendation, optional design, later-slice re-entry, high-risk review blocking, and unchanged archive safety.
- tests/test_renderers.py — replace assertions that enforce global per-phase interactive stops/all-artifacts review with assertions for slice checkpoints and high-risk escalation.

## Plan
- Define the smallest disk-derived slice contract: PRD capability order is authoritative; one selected capability has its spec and tasks, and its completed tasks plus slice validation permit either the next capability or final archive. Do not add deterministic receipts or a new task-ledger/DAG.
- Extend status derivation and its public JSON schema only as required to name the current/next capability and a slice-level route. Preserve existing artifact paths, task CLI operations, and archive requirement that all known tasks are complete and final validation exists.
- Revise coordinator and phase prompts so exploration/PRD establish a thin first capability, then spec → tasks → implement → validate runs for that capability. Cross-cutting design is required only when the slice or declared risk warrants it.
- Replace per-phase interactive approval with a capability-bound feedback checkpoint: normal-risk auto flow may reach a working, validated first slice; interactive flow reviews at slice boundaries. Require explicit review before implementation for high-risk classifications and whenever scope changes.
- Add focused state and rendered-prompt tests, then update expected fixtures and run the relevant pytest and formatter/linter gates.

## Edge Cases
- A one-capability change must route from its slice validation to final validation/archive, not request a nonexistent next slice.
- A PRD capability with no spec or tasks must remain planning work; an empty tasks file must not make a slice complete.
- A later capability may depend on earlier delivered behavior, but this slice must not introduce general DAG scheduling; preserve current task dependency validation within the selected task set.
- Editing the PRD capability list, selected spec, or completed-slice task set after approval invalidates normal-flow approval and reopens the applicable review gate.
- Cross-cutting, security, migration, public-API, or explicitly high-risk work must require change-wide design and explicit human approval before implementation.
- Legacy changes with only the existing global artifacts must continue to derive a safe route or receive clear migration/review guidance; they must never become archiveable merely because a slice marker is absent.

## Test Surface
- Unit/CLI status tests for first-slice selection, optional-design normal path, selected-slice task completion, next-slice routing, final routing, malformed/missing slice inputs, and compatibility with legacy artifact layouts.
- Archive tests proving all tasks and final validation are still required, independent of earlier slice validations.
- Render tests asserting a capability checkpoint replaces universal phase checkpoints, normal-risk first-slice feedback is allowed, and high-risk work retains explicit design/review controls.
- Resource rendering/expected-fixture parity across OpenCode, Claude, and Copilot.

## Risks
- The current FSM has one global artifact per phase and considers any spec/tasks/implementation artifact complete; prompt-only edits would falsely claim capability delivery while still routing linearly. Mitigate by making the minimal slice identity and completion state disk-derived before changing prompts.
- A slice manifest or task grouping can accidentally become the deferred task-ledger/DAG. Mitigate by storing only ordered PRD capability identity and selected-slice completion facts; defer dependency graph, receipts, and generalized scheduling.
- Adding route tokens or status fields is a public JSON/config-context compatibility risk. Mitigate with an additive schema version, explicit legacy behavior, and focused serialization tests.
- Relaxing reviews could bypass safety controls. Mitigate with conservative high-risk classification, explicit approval for high-risk/cross-cutting scope, and unchanged archive/task-completion/validation guards.

## Semantic Facts
- budget: 610
- follow_up: Decide the disk representation for selected/completed capability slices, define the high-risk classifier and approval policy, and specify legacy-change migration/compatibility before task decomposition.
