# Spec — Render/test contract hardening

## Purpose

Ensure renderer tests verify concrete orchestrator behavior rather than vague keyword presence, including all gentle-orchestrator parity references:

- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-149`
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-199`
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:200`
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:202-222`
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:299-308`

## Requirements

### Requirement: Tests assert behavior invariants, not mere keywords
The system MUST harden renderer tests to assert concrete control-flow behavior for `change-orchestrator`.

#### Scenario: Pause keyword without STOP fails
GIVEN rendered prompt text mentions `interactive` and `pause`
WHEN it does not require report, ask, STOP, and wait after every delegated phase
THEN the renderer test fails.

#### Scenario: Approval keyword without phase scope fails
GIVEN rendered prompt text mentions approval
WHEN it does not state approval is scoped only to the immediate next phase
THEN the renderer test fails.

### Requirement: Tests cover observed interactive failure
The system MUST include tests that catch launching PRD in the same turn after interactive exploration.

#### Scenario: Explore nextRecommended PRD must wait
GIVEN cached mode is interactive in the rendered behavior contract
AND explore completes with `nextRecommended` as `prd`
WHEN the orchestrator receives the phase result
THEN expected behavior is report-and-wait
AND any prompt contract that allows same-turn PRD launch fails the test.

### Requirement: Tests cover phase-scoped continue
The system MUST assert that `continue` after PRD authorizes only design, not specs or tasks.

#### Scenario: Continue after PRD is not pipeline approval
GIVEN rendered behavior describes interactive checkpoints
WHEN the test searches for approval semantics
THEN it finds wording that `continue` after PRD authorizes design only and requires another checkpoint before specs or tasks.

### Requirement: Tests cover grill/proposal-question gate
The system MUST assert the prompt preserves a grill/proposal-question gate for weak understanding and unclear intent.

#### Scenario: Ambiguous archive request requires clarification
GIVEN rendered prompt text includes unclear intent handling
WHEN the request could mean manual archive or CLI archive implementation
THEN expected behavior is clarification before PRD or implementation assumptions.

### Requirement: Tests cover explicit auto-mode gatekeeper
The system MUST assert automatic mode requires explicit or cached auto mode plus contract, artifact, no-drift, and routing checks.

#### Scenario: Auto default fall-through fails
GIVEN rendered prompt text describes automatic mode
WHEN it allows auto-continuation without explicit or cached auto mode
THEN the renderer test fails.

#### Scenario: Missing gatekeeper checks fail
GIVEN rendered prompt text says auto continues phases
WHEN it omits contract, artifact, no-drift, or routing checks
THEN the renderer test fails.

### Requirement: Tests preserve launch deduplication reference
The system MUST assert the rendered prompt contains session `(phase, task-fingerprint)` launch deduplication behavior.

#### Scenario: Duplicate guard omitted
GIVEN rendered prompt text delegates phases
WHEN it lacks a session launch log that blocks repeated `(phase, task-fingerprint)` launches
THEN the renderer test fails.

### Requirement: Tests preserve all gentle reference line ranges
The system MUST assert all required gentle-orchestrator line references remain present in the rendered prompt or associated Change artifacts.

#### Scenario: Missing gentle reference fails
GIVEN rendered prompt or Change artifact text is inspected
WHEN any required gentle-orchestrator reference line range is absent
THEN the test fails and reports the missing reference.
