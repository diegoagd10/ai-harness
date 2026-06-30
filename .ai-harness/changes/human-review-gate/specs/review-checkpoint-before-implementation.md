# Spec — Review checkpoint before implementation

## Purpose

Ensure `change-orchestrator` gives the human an explicit review opportunity after planning artifacts are ready and before any implementation agent can run.

## Requirements

### Requirement: Wait after reviewable artifacts exist

The system MUST stop at a human review checkpoint after PRD, design, specs, and tasks are ready and before launching `change-implementor`.

#### Scenario: Complete artifacts trigger review wait

GIVEN a Change has PRD, design, specs, and tasks artifacts present
WHEN `change-orchestrator` reaches the implementation routing point
THEN it returns a waiting result that asks the human to review those artifacts.

#### Scenario: Implementor is not launched before review

GIVEN a Change has complete planning artifacts but no explicit human continuation confirmation
WHEN `change-orchestrator` evaluates the next action
THEN it MUST NOT launch `change-implementor`.

### Requirement: Earlier blockers remain earlier

The system MUST check missing PRD, design, specs, or tasks before presenting the human review gate.

#### Scenario: Missing tasks block before review

GIVEN a Change has PRD, design, and specs but no tasks artifact
WHEN `change-orchestrator` evaluates the next action
THEN it routes to task creation or reports the missing tasks blocker instead of asking for implementation review.

### Requirement: Parent decomposition is not treated as implementation

The system SHOULD avoid applying the implementation review gate to parent large-change decomposition work that is still planning, not code implementation.

#### Scenario: Parent split continues planning flow

GIVEN a parent Change needs decomposition into executable child Changes
WHEN `change-orchestrator` routes the parent planning work
THEN it does not block decomposition solely because the implementation review gate exists.
