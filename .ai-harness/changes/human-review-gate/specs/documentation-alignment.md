# Spec — Documentation alignment

## Purpose

Ensure design documentation matches the review gate behavior, routing order, resume semantics, and schema decision.

## Requirements

### Requirement: Document routing order

The system MUST document that artifact prerequisite checks happen before the human review checkpoint, and implementation happens only after explicit confirmation.

#### Scenario: Maintainer reads flow docs

GIVEN a maintainer opens the change-orchestrator design documentation
WHEN they inspect the artifact-to-implementation flow
THEN the docs show missing artifact handling before review and `change-implementor` after approval.

### Requirement: Document resume semantics

The system MUST document resume behavior for prompt-only waiting and for any future durable approval marker if introduced.

#### Scenario: Prompt-only resume is documented

GIVEN no persisted approval marker is implemented
WHEN a maintainer reads the docs
THEN the docs explain that resumed orchestration re-prompts safely for human review.

#### Scenario: Durable marker is introduced later

GIVEN a future implementation adds persisted approval state
WHEN the docs are updated
THEN they explain how the marker is tied to the reviewed artifact set and how stale approval reopens the gate.

### Requirement: Document schema restraint

The system SHOULD explain why no new status token or schema field is added unless durable approval becomes necessary.

#### Scenario: Maintainer evaluates status changes

GIVEN a maintainer considers adding a new review status
WHEN they read the documentation
THEN they see that prompt-level `waiting` is the preferred first implementation and schema changes are reserved for proven durability needs.

### Requirement: Document parent decomposition nuance

The system SHOULD document that parent large-change decomposition is planning work and should not be accidentally blocked by the implementation review gate.

#### Scenario: Parent Change flow is maintained

GIVEN documentation describes parent and child Change routing
WHEN a maintainer updates decomposition behavior
THEN they can distinguish parent planning decomposition from child implementation gating.
