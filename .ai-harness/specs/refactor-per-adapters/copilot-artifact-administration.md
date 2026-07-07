# Spec — Copilot artifact administration

## Purpose

Prove `CopilotArtifactsAdministrator` owns prompt rendering and the corrected Copilot path layout while preserving intentionally minimal Copilot metadata semantics.

## Requirements

### Requirement: Copilot renders stable agent paths
The system MUST render Copilot artifacts to `.copilot/agents/<name>.agent.md`, preserving the design correction from the PRD's `.github/instructions/...` text.

#### Scenario: Copilot change explorer renders existing path
GIVEN a `change-explorer` metadata JSON and template body
WHEN `CopilotArtifactsAdministrator.render_artifacts(["change-explorer"], overrides={}, home=home)` is called
THEN it produces an `Artifact` whose `install_path` is `.copilot/agents/change-explorer.agent.md` and whose content includes the rendered template body.

### Requirement: Copilot frontmatter is minimal
The system MUST render only ordered `name` and `description` frontmatter for Copilot and MUST NOT emit model, effort, tools, permission, mode, color, `user-invocable`, or `disable-model-invocation` fields.

#### Scenario: Metadata with provider extras remains minimal
GIVEN metadata containing `mode`, `model`, `effort`, `caps`, `permission`, and `color`
WHEN `CopilotArtifactsAdministrator.render_artifacts([name], overrides={}, home=home)` is called
THEN the frontmatter contains only `name` and `description` before the template body.

### Requirement: Copilot does not require provider model
The system MUST NOT require `model.copilot` for Copilot rendering.

#### Scenario: Missing model.copilot succeeds
GIVEN a `change-explorer` metadata JSON without `model.copilot`
WHEN `CopilotArtifactsAdministrator.render_artifacts(["change-explorer"], overrides={}, home=home)` is called
THEN no `ValueError` is raised for the missing Copilot model.
