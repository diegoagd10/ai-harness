# Spec — Approval-controlled continuation

## Purpose

Ensure implementation starts only after the human explicitly confirms they are ready to continue past the review checkpoint.

## Requirements

### Requirement: Explicit confirmation required

The system MUST require explicit human confirmation before moving from the review checkpoint to `change-implementor`.

#### Scenario: Human confirms continuation

GIVEN `change-orchestrator` has already presented the review checkpoint for current artifacts
WHEN the human explicitly confirms continuation
THEN `change-orchestrator` may launch `change-implementor` for that Change.

#### Scenario: Ambiguous response does not approve

GIVEN `change-orchestrator` is waiting at the review checkpoint
WHEN the human responds with feedback, questions, or an ambiguous acknowledgement that does not clearly approve implementation
THEN the system remains waiting and MUST NOT launch `change-implementor`.

### Requirement: Review request names artifacts

The system SHOULD name the PRD, design, specs, and tasks artifacts in the review checkpoint so the human knows what to review.

#### Scenario: Review prompt is actionable

GIVEN the planning artifacts are complete
WHEN the review checkpoint is presented
THEN the message identifies PRD, design, specs, and tasks as the artifacts under review.

### Requirement: No separate approval surface by default

The system SHOULD use conversational confirmation rather than requiring a new approval UI, command, or external tracker artifact.

#### Scenario: Confirmation happens in orchestrator conversation

GIVEN the human has reviewed the artifacts
WHEN they confirm continuation in the current orchestrator conversation
THEN the system accepts that confirmation without requiring a separate approval command.
