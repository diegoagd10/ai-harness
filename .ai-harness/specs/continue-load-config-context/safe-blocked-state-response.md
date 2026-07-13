# Spec — Safe blocked-state response

## Purpose

Represent an unroutable continuation explicitly without inventing a configuration phase or dispatch context.

## Requirements

### Requirement: Return null context for blocker resolution
The system MUST return `configContext: null` when `nextRecommended` is `resolve-blockers` and MUST NOT call `ChangeConfigAdministrator.get_context_by` with that synthetic token.

#### Scenario: Return a successful blocked status
GIVEN a change whose lifecycle status has unresolved blockers and derives `nextRecommended: "resolve-blockers"`
WHEN `ai-harness change-continue <change>` is invoked
THEN it succeeds with the normal status fields, `nextRecommended: "resolve-blockers"`, and `configContext: null`.

#### Scenario: Bypass configuration for a blocked route
GIVEN a change derives `resolve-blockers` and repository configuration is unavailable or malformed
WHEN `ai-harness change-continue <change>` is invoked
THEN it does not validate or request phase context and returns the blocked status rather than treating the synthetic token as a configuration phase.

### Requirement: Prevent blocked-state sub-agent routing
The system SHOULD document and expose null context as the sole continuation context for `resolve-blockers` so consumers do not dispatch a sub-agent for that state.

#### Scenario: Consume a blocked response
GIVEN an orchestrator receives a successful continuation response with `nextRecommended: "resolve-blockers"`
WHEN it evaluates the response for sub-agent work
THEN it has no context object to forward and does not select a routed phase agent.
