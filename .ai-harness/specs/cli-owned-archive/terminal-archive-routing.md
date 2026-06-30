# Spec — Terminal archive routing

## Purpose

Keep semantic archive readiness in the orchestrator while delegating physical archive execution to `change-archiver`, with terminal success and human-blocked failure.

## Requirements

### Requirement: Orchestrator retains semantic validation gate
The orchestrator MUST inspect semantic validation output and decide whether archive is allowed before spawning `change-archiver`.

#### Scenario: Semantic gate blocks archive
GIVEN validation output contains unresolved critical semantic findings
WHEN the orchestrator evaluates archive readiness
THEN it does not spawn `change-archiver`
AND it routes the Change back to the appropriate continuation or human decision flow.

#### Scenario: Semantic gate passes archive candidate
GIVEN validation output shows the Change is semantically ready to archive
WHEN the orchestrator evaluates archive readiness
THEN it may spawn `change-archiver`.

### Requirement: Orchestrator delegates archive execution
The orchestrator MUST spawn `change-archiver` for archive execution and MUST NOT include manual filesystem move instructions for archiving.

#### Scenario: Archive routed to archiver
GIVEN the semantic gate passes for `example`
WHEN the orchestrator enters archive routing
THEN it spawns `change-archiver` with the target Change context.

#### Scenario: Orchestrator does not own file moves
GIVEN the orchestrator prompt is rendered
WHEN archive instructions are inspected
THEN they do not instruct the orchestrator to move `.ai-harness/changes/example/specs/` or `.ai-harness/changes/example/` manually.

### Requirement: Successful archive is terminal
The orchestrator MUST treat a successful `change-archiver` result as terminal and MUST NOT run `change-continue` after archive success.

#### Scenario: Archiver success ends flow
GIVEN `change-archiver` reports success for `example`
WHEN the orchestrator handles the result
THEN the archive flow ends
AND no post-archive `change-continue` command is invoked.

### Requirement: Archiver failure blocks for human decision
The orchestrator MUST mark the archive flow blocked and ask the human for intervention when `change-archiver` fails.

#### Scenario: Archiver blocked result escalates
GIVEN `change-archiver` returns blocked with archive errors
WHEN the orchestrator handles the result
THEN it reports the archive failure as blocked
AND asks the human to decide how to proceed.

### Requirement: Routing prompt rendering coverage
The system MUST test rendered orchestrator archive routing for semantic gate preservation, `change-archiver` spawning, terminal success, and blocked failure behavior.

#### Scenario: Rendered orchestrator contains archive route
GIVEN change-agent prompts are rendered
WHEN renderer coverage inspects `change-orchestrator.md`
THEN it includes the semantic gate before archive spawning
AND references `change-archiver`
AND describes success as terminal
AND describes archiver failure as blocked human intervention.
