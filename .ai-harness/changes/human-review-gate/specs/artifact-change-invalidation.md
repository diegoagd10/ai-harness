# Spec — Artifact-change invalidation

## Purpose

Ensure approval never applies to stale planning artifacts after PRD, design, specs, or tasks are changed.

## Requirements

### Requirement: Changed artifacts reopen gate

The system MUST treat approval as absent when PRD, design, specs, or tasks change after a review request or approval and before implementation starts.

#### Scenario: Tasks change after review request

GIVEN the human review checkpoint was presented for a complete artifact set
WHEN `tasks.json` changes before `change-implementor` starts
THEN `change-orchestrator` presents the review checkpoint again before implementation.

#### Scenario: Design changes after approval

GIVEN the human explicitly approved implementation for a complete artifact set
WHEN `design.md` changes before implementation starts
THEN prior approval is stale and the system waits for renewed human confirmation.

### Requirement: Durable markers bind to artifact revision if introduced

The system MUST bind any persisted approval marker to the reviewed artifact revision or digest set, not merely to the Change name.

#### Scenario: Persisted marker does not match changed specs

GIVEN durable approval exists for a previous specs artifact revision
WHEN the specs artifact changes before implementation
THEN the durable marker is ignored and the review gate reopens.

### Requirement: Unchanged artifacts keep current conversation approval

The system MAY continue after explicit confirmation when the reviewed artifacts have not changed before implementation starts.

#### Scenario: Approved artifacts stay stable

GIVEN the human approved implementation for the current PRD, design, specs, and tasks
WHEN no reviewed artifact changes before routing continues
THEN `change-orchestrator` may launch `change-implementor`.
