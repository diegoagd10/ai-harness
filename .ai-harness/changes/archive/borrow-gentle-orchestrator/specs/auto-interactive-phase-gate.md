# Spec — auto/interactive phase gate

## Purpose

Match gentle-ai-style phase gating by making auto vs interactive mode explicit, stable for the session, and safe before implementation.

Traceability: PRD capability “Auto vs interactive phase gate”; design seam “Auto/interactive phase gate”; evidence `gentle-ai:docs/opencode-profiles.md:11-12, 64-66`, `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:98-108, 182-220`, `ai-harness:docs/design/change-orchestrator.md:173-258, 260-316, 394-423`, `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:58-108`.

## Requirements

### Requirement: Mode is explicit and stable
The system MUST establish a session mode of `auto` or `interactive` from command/profile context or explicit user instruction and keep that mode stable for the session.

#### Scenario: Interactive mode selected
GIVEN command/profile context or user instruction selects interactive behavior
WHEN orchestration begins
THEN the session mode is recorded or stated as `interactive`

#### Scenario: Auto mode selected
GIVEN command/profile context or user instruction selects automatic progression
WHEN orchestration begins
THEN the session mode is recorded or stated as `auto`

#### Scenario: Mode does not drift mid-session
GIVEN a session mode has been established
WHEN later phase gates execute
THEN the same mode applies unless the user explicitly starts a new session or changes mode through supported flow

### Requirement: Interactive gates pause for user review
The system MUST pause at interactive phase gates for user review, especially before implementation.

#### Scenario: Interactive pauses before implementation
GIVEN the session mode is `interactive`
WHEN exploration, design, specs, or tasks are ready for implementation
THEN the workflow pauses for user review before any implementor delegation

#### Scenario: Interactive waits across phase boundary
GIVEN the session mode is `interactive`
WHEN a phase completes successfully
THEN the orchestrator asks for user review or confirmation before advancing across the next gated boundary

### Requirement: Auto gates continue only when safe
The system MAY continue automatically only when the prior phase passes, required review is current, and no blocked semantic facts exist.

#### Scenario: Auto continues after safe pass
GIVEN the session mode is `auto`, prior phase status is pass, required review is current, and semantic facts are not blocked
WHEN the phase gate evaluates progression
THEN the orchestrator may continue to the next phase

#### Scenario: Auto stops on failed or blocked facts
GIVEN the session mode is `auto`
WHEN prior phase status fails or semantic facts show blocked/critical state
THEN the orchestrator stops and reports the blocking reason

#### Scenario: Auto does not bypass review
GIVEN the session mode is `auto` and implementation requires current artifact review
WHEN review is missing or stale
THEN the orchestrator does not start implementation

### Requirement: Regression coverage for phase gates
The system SHOULD include render or state tests that lock mode source, caching, and phase gate behavior.

#### Scenario: Render test locks interactive pause
GIVEN renderer tests execute
WHEN `change-orchestrator` is rendered
THEN assertions cover mandatory interactive pause before implementation

#### Scenario: Render test locks auto safety conditions
GIVEN renderer tests execute
WHEN `change-orchestrator` is rendered
THEN assertions cover auto progression only after pass, current review, and unblocked semantic facts

#### Scenario: State test locks mode if persisted
GIVEN implementation persists session mode
WHEN change module tests execute
THEN tests verify mode remains stable across the intended session or resume boundary
