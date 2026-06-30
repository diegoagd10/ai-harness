# Spec — start/resume contract

## Purpose

Make change orchestration enter through explicit `change-new` and `change-continue` routes backed by disk state, not prompt-level folder guessing.

Traceability: PRD capability “Start/resume contract”; design seam “Start/resume route contract”; evidence `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:3-25`, `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:3-29`, `ai-harness:src/ai_harness/modules/harness/change.py:45-89`, `ai-harness:tests/test_change.py:19-57, 78-123, 126-157`.

## Requirements

### Requirement: Explicit route authority
The system MUST treat `change-new` as the only start route and `change-continue` as the only resume route for a file-backed change.

#### Scenario: New change starts through start route
GIVEN no disk-backed change exists for a requested change name
WHEN the user enters through `change-new`
THEN orchestration starts that change as a new file-backed change

#### Scenario: Existing change resumes through resume route
GIVEN a disk-backed change exists for a requested change name
WHEN the user enters through `change-continue`
THEN orchestration resumes the existing change instead of starting a new one

### Requirement: Disk state is authoritative
The system MUST use disk state as the authority for whether a change exists and MUST NOT infer start or resume mode from loose folder-presence guesses inside the prompt.

#### Scenario: Prompt receives route contract
GIVEN the orchestrator prompt is rendered for a change session
WHEN it describes start and resume behavior
THEN it states that command route plus disk state determine start/resume mode

#### Scenario: Folder guess is rejected
GIVEN prompt context contains ambiguous filesystem hints
WHEN the route is not proven by `change-new` or `change-continue` semantics
THEN orchestration blocks instead of guessing mode from folder presence

### Requirement: Ambiguous routes block implementation
The system MUST block progression toward implementation when start/resume route facts are ambiguous, colliding, or missing.

#### Scenario: New route collides with existing change
GIVEN a disk-backed change already exists
WHEN the user enters through `change-new` for that name
THEN the system blocks with clear recovery guidance instead of overwriting or resuming implicitly

#### Scenario: Continue route targets missing change
GIVEN no disk-backed change exists
WHEN the user enters through `change-continue` for that name
THEN the system blocks with clear recovery guidance instead of creating it implicitly

### Requirement: Regression coverage for route contract
The system SHOULD include regression coverage for rendered route wording and any CLI/state collision or missing-change semantics that change.

#### Scenario: Render test locks route wording
GIVEN prompt rendering tests run
WHEN `change-orchestrator` is rendered
THEN assertions cover explicit start/resume routing, disk authority, and no ambiguous implementation start

#### Scenario: State tests cover changed route errors
GIVEN implementation changes CLI or state behavior for route errors
WHEN change tests run
THEN tests cover existing-change collision and missing-change resume behavior
