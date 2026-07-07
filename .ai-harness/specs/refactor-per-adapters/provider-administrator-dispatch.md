# Spec — Provider administrator dispatch

## Purpose

Prove callers can select a provider administrator through `ADMINISTRATORS[AgentCli.X]` and use the shared `ArtifactsAdministrator.render_artifacts(...)` contract without branching on provider internals. This spec references the design contracts for `ArtifactsAdministrator`, `ADMINISTRATORS`, and `Artifact`.

## Requirements

### Requirement: Dispatch table exposes supported administrators
The system MUST expose `ADMINISTRATORS` keyed by `AgentCli.CLAUDE`, `AgentCli.OPENCODE`, and `AgentCli.COPILOT`, with values implementing `ArtifactsAdministrator`.

#### Scenario: Render through provider-agnostic dispatch
GIVEN a home directory and discovered `change-explorer` metadata and template resources
WHEN a caller invokes `ADMINISTRATORS[AgentCli.OPENCODE].render_artifacts(["change-explorer"], overrides={}, home=home)`
THEN the caller receives `Artifact` results without importing or branching on OpenCode-specific rendering helpers.

#### Scenario: Unsupported generic CLI has no administrator
GIVEN the `ADMINISTRATORS` dispatch table
WHEN a caller checks `ADMINISTRATORS.get(AgentCli.GENERIC)`
THEN no administrator is returned and the caller can treat generic rendering as a no-op.

### Requirement: Administrators share a common rendering signature
Each administrator MUST support `render_artifacts(names=None, overrides=None, *, home=None) -> list[Artifact]` with consistent argument semantics.

#### Scenario: Same call shape works across providers
GIVEN a home directory and the name `change-explorer`
WHEN Claude, OpenCode, and Copilot administrators are each called with `render_artifacts(["change-explorer"], overrides={}, home=home)`
THEN each call returns provider-specific `Artifact` objects through the same method shape.
