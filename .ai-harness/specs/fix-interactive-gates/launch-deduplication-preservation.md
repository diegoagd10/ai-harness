# Spec — Launch deduplication preservation

## Purpose

Preserve duplicate sub-agent launch prevention with a session `(phase, task-fingerprint)` log, carrying forward `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:299-308`.

## Requirements

### Requirement: Check launch log before delegation
The system MUST check a session-scoped launch log before every sub-agent delegation.

#### Scenario: First launch is recorded
GIVEN no launch log entry exists for phase `prd` and the current task fingerprint
WHEN the orchestrator launches the PRD phase
THEN it records `(prd, task-fingerprint)` in the session launch log.

### Requirement: Block duplicate launch in same session
The system MUST NOT launch a second sub-agent for the same `(phase, task-fingerprint)` pair in the same session.

#### Scenario: Duplicate retry is blocked
GIVEN the session launch log already contains `(design, abc123)`
WHEN the orchestrator attempts to launch design again with fingerprint `abc123`
THEN it blocks the duplicate launch and reports or reuses the prior result.

#### Scenario: Rephrased same task is blocked
GIVEN the user rephrases the same PRD continuation request
AND fingerprint normalization produces the same task fingerprint
WHEN the orchestrator prepares to delegate PRD
THEN the duplicate guard blocks a second PRD launch.

### Requirement: Distinct tasks may launch
The system MAY launch the same phase again when the task fingerprint is meaningfully different.

#### Scenario: Adjusted artifact creates new fingerprint
GIVEN a prior specs launch used fingerprint `old-scope`
AND the user explicitly changes scope after reviewing specs
WHEN the orchestrator computes fingerprint `new-scope`
THEN the launch guard allows the new specs delegation and records it.
