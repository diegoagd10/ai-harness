# Spec — Resume-safe review behavior

## Purpose

Keep resumed orchestration safe by preventing implementation from starting unless approval for the current artifact set is available.

## Requirements

### Requirement: Conservative resume without persistence

The system MUST re-present the human review checkpoint on resume when no durable approval marker exists for the current artifacts.

#### Scenario: Resume after session gap

GIVEN a Change has complete planning artifacts and no persisted approval marker
WHEN `change-orchestrator` resumes after a session gap or compaction
THEN it waits again for human review confirmation before implementation.

### Requirement: Durable approval may be honored if introduced

The system MAY honor a durable approval marker only when the marker applies to the current PRD, design, specs, and tasks.

#### Scenario: Current artifacts match persisted approval

GIVEN durable approval state exists for the current artifact set
WHEN `change-orchestrator` resumes at the implementation routing point
THEN it may continue to `change-implementor` without re-requesting review.

#### Scenario: Approval marker is absent

GIVEN durable approval state is supported but no approval marker exists for the Change
WHEN `change-orchestrator` resumes at the implementation routing point
THEN it presents the human review checkpoint.

### Requirement: Prompt-only gate remains acceptable

The system SHOULD avoid adding schema or status tokens unless prompt-only waiting cannot provide acceptable resume behavior.

#### Scenario: No durable marker needed

GIVEN prompt-level waiting safely re-prompts after resume
WHEN implementing the review gate
THEN no new Change schema token or persisted approval field is required.
