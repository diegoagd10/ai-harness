# Spec — Archive Command Contract

## Purpose

Define archive as an explicit orchestrator command with observable invocation rules, required inputs, allowed states, blocked states, and final reporting behavior.

## Requirements

### Requirement: CLI route authority
The system MUST invoke archive handling only from `ai-harness change-continue {change}` output that recommends `nextRecommended: archive`.

#### Scenario: CLI recommends archive
GIVEN `ai-harness change-continue archive-command` reports `nextRecommended: archive`
WHEN the orchestrator evaluates the next action
THEN it treats archive as the active command candidate and evaluates archive preconditions.

#### Scenario: CLI recommends a different action
GIVEN `ai-harness change-continue archive-command` reports a next recommendation other than `archive`
WHEN the orchestrator evaluates the next action
THEN it MUST NOT infer archive readiness from files or folders.

### Requirement: Command contract content
The system MUST describe archive with clear purpose, inputs, allowed states, blocked states, and side-effect boundaries in the orchestrator prompt.

#### Scenario: Agent reads archive contract
GIVEN the orchestrator prompt is rendered
WHEN an agent reaches the archive command section
THEN the prompt explains what archive does, what inputs it consumes, when it may proceed, when it must block, and which side effects are forbidden.

### Requirement: Final result block
The system MUST require archive command completion to return a final result block that states status, artifacts, summary, semantic facts, and skills.

#### Scenario: Archive completes
GIVEN archive preconditions are satisfied
WHEN the orchestrator reports completion
THEN it returns a final result block with `status: done`, archive-related artifacts, a one-line summary, `semantic_facts.waiting: false`, and `skills` status.

#### Scenario: Archive blocks
GIVEN archive preconditions are not satisfied
WHEN the orchestrator reports completion
THEN it returns a final result block with a blocked or waiting status and a summary naming the blocking condition.
