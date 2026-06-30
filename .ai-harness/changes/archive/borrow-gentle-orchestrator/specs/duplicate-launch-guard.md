# Spec — duplicate-launch guard

## Purpose

Prevent duplicate same-turn or same-session delegation for the same phase and task fingerprint.

Traceability: PRD capability “Duplicate-launch guard”; design seam “Delegation launch ledger”; evidence `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:182-220`, `gentle-ai:internal/cli/run_integration_test.go:2062-2075`, `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:110-166`.

## Requirements

### Requirement: Launch log keyed by phase and fingerprint
The system MUST maintain a session-scoped launch log keyed by `(phase, task_fingerprint)` before delegating work.

#### Scenario: First launch records key
GIVEN no launch log entry exists for a phase and task fingerprint
WHEN the orchestrator delegates that work
THEN it records the `(phase, task_fingerprint)` key before or at launch

#### Scenario: Fingerprint includes meaningful work identity
GIVEN the orchestrator prepares a delegation
WHEN it computes `task_fingerprint`
THEN the fingerprint reflects phase, target artifacts, and requested work

### Requirement: Duplicate launches are refused
The system MUST refuse to launch a second subagent for the same `(phase, task_fingerprint)` in the same turn or session context.

#### Scenario: Same key is refused
GIVEN a launch log already contains `(phase, task_fingerprint)`
WHEN the orchestrator attempts the same delegation again
THEN it returns blocked or waiting guidance instead of launching another subagent

#### Scenario: Changed fingerprint can launch
GIVEN a launch log contains a key for previous work
WHEN artifacts or requested work meaningfully change and produce a new fingerprint
THEN the orchestrator may delegate the new work

### Requirement: Guard degrades safely when prompt memory is insufficient
The system SHOULD add CLI/state support if prompt/session memory cannot reliably enforce duplicate-launch refusal across the required context.

#### Scenario: Prompt-only guard is sufficient
GIVEN session memory reliably tracks the launch log
WHEN duplicate delegation is attempted
THEN the prompt-level guard blocks the duplicate

#### Scenario: Prompt memory is insufficient
GIVEN duplicate launch prevention cannot survive the required session context in prompt memory
WHEN implementation needs stronger enforcement
THEN disk-backed state support is added with targeted tests

### Requirement: Regression coverage for duplicate guard
The system SHOULD include regression coverage for duplicate-launch wording or persisted refusal semantics.

#### Scenario: Render test locks duplicate wording
GIVEN renderer tests execute
WHEN `change-orchestrator` is rendered
THEN assertions cover launch log keying and duplicate refusal

#### Scenario: State test locks persisted duplicate behavior
GIVEN implementation persists launch keys
WHEN the same phase/task key is launched twice
THEN change tests verify the second launch is refused
