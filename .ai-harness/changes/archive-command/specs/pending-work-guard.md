# Spec — Pending Work Guard

## Purpose

Prevent archive when any tasks remain incomplete, regardless of validator outcome.

## Requirements

### Requirement: Pending tasks block archive
The system MUST block archive when task progress reports any incomplete work.

#### Scenario: Validation passes but tasks remain
GIVEN validator semantic facts are `verdict: pass` and `critical: 0`
AND task progress reports pending tasks
WHEN archive handling evaluates preconditions
THEN archive is blocked and the orchestrator routes back to implementation.

#### Scenario: Validation passes with warnings but tasks remain
GIVEN validator semantic facts are `verdict: pass-with-warnings` and `critical: 0`
AND task progress reports pending tasks
WHEN archive handling evaluates preconditions
THEN archive is blocked and warnings do not override the pending-work guard.

### Requirement: Complete tasks permit semantic gate evaluation
The system MUST treat zero pending tasks as necessary but not sufficient for archive.

#### Scenario: No pending work
GIVEN task progress reports no pending tasks
WHEN archive handling evaluates preconditions
THEN it still applies validator semantic gate checks before allowing archive.

### Requirement: Missing task progress is not archive-ready
The system SHOULD block archive when task progress cannot confirm all work is complete.

#### Scenario: Task progress unavailable
GIVEN the orchestrator cannot confirm that all tasks are complete
WHEN archive handling evaluates preconditions
THEN archive is blocked until `ai-harness change-continue {change}` provides reliable task progress.
