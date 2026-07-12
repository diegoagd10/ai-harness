# Spec — Orchestrator context forwarding

## Purpose

Make the documented orchestrator contract forward CLI-delivered context directly to the selected sub-agent.

## Requirements

### Requirement: Document the complete version-2 continuation contract
The system MUST update the source orchestrator prompt, its rendered expectation, and active CLI-contract documentation to describe `configContext` as a nullable version-2 `ChangeStatus` field.

#### Scenario: Document the representative proposal response
GIVEN the orchestrator documentation presents a routed `prd` continuation example
WHEN a reader parses the complete JSON response
THEN it contains `schemaVersion: 2`, `nextRecommended: "prd"`, and `configContext.phase: "change_propose"` with ordered `phase_rules`.

#### Scenario: Keep rendered documentation synchronized
GIVEN the source orchestrator prompt is updated for this contract
WHEN rendered expectations are checked
THEN the checked-in rendered expectation contains the same version-2 context shape and forwarding instruction.

### Requirement: Forward returned context without independent configuration access
The orchestrator MUST forward `configContext` unchanged to the sub-agent selected by actionable `nextRecommended` and MUST NOT independently read configuration or reconstruct phase aliases.

#### Scenario: Forward routed proposal context
GIVEN `change-continue` returns `nextRecommended: "prd"` and a populated `configContext`
WHEN the orchestrator invokes the selected proposal sub-agent
THEN it supplies that exact context object to the sub-agent.

#### Scenario: Do not forward blocked context
GIVEN `change-continue` returns `nextRecommended: "resolve-blockers"` and `configContext: null`
WHEN the orchestrator processes the response
THEN it does not invoke a routed sub-agent and does not independently load configuration.
