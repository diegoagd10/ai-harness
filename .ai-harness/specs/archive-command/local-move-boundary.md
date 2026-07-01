# Spec — Local Move Boundary

## Purpose

Define archive as a local filesystem operation only, with no git, branch, PR, publishing, issue-tracker, or remote side effects.

## Requirements

### Requirement: Local filesystem scope
The system MUST define archive as a local move of change artifacts and specs only.

#### Scenario: Archive proceeds
GIVEN archive preconditions are satisfied
WHEN archive behavior is described to an agent
THEN it is described as moving local change files, not as publishing or landing work.

### Requirement: Git and branch side effects forbidden
The system MUST NOT imply that archive commits, stages files, switches branches, creates branches, pushes, or opens pull requests.

#### Scenario: Agent reaches archive phase
GIVEN the archive command contract is rendered
WHEN the agent reads the side-effect boundary
THEN it sees that git commits, branch operations, pushes, and PR creation are excluded.

### Requirement: Remote publishing forbidden
The system MUST NOT imply that archive publishes issues, updates remote trackers, or performs remote side effects.

#### Scenario: Archive follows issue-backed planning
GIVEN the change may have PRD, design, or issue-related artifacts
WHEN archive is allowed
THEN the orchestrator still treats archive as local-only and does not publish to GitHub or any remote system.

### Requirement: Execution details remain outside prompt contract
The system SHOULD avoid specifying exact move order, collision handling, or future archive implementation mechanics in the orchestrator prompt.

#### Scenario: Prompt documents archive
GIVEN archive command wording is updated
WHEN implementation-specific details are considered
THEN the prompt states the local-only boundary without taking ownership of CLI execution mechanics.
