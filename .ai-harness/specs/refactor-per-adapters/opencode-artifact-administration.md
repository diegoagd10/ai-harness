# Spec — OpenCode artifact administration

## Purpose

Prove `OpenCodeArtifactsAdministrator` owns discovery, metadata decoding, override merging, OpenCode frontmatter, permission derivation, explicit permission precedence, color passthrough, and `.config/opencode/agent/...` install paths.

## Requirements

### Requirement: OpenCode renders agent artifacts
The system MUST render OpenCode artifacts to `.config/opencode/agent/<name>.md` and MUST require `model.opencode`.

#### Scenario: OpenCode change explorer renders installable artifact
GIVEN a `change-explorer` metadata JSON with `description`, `mode`, and `model.opencode`
WHEN `OpenCodeArtifactsAdministrator.render_artifacts(["change-explorer"], overrides={}, home=home)` is called
THEN it produces an `Artifact` whose `install_path` is `.config/opencode/agent/change-explorer.md` and whose frontmatter includes `description`, `mode`, and `model`.

#### Scenario: Missing OpenCode model fails loudly
GIVEN a visible template whose metadata JSON lacks `model.opencode`
WHEN `OpenCodeArtifactsAdministrator.render_artifacts([name], overrides={}, home=home)` is called
THEN a `ValueError` is raised naming the missing provider model.

### Requirement: OpenCode frontmatter preserves provider semantics
The system MUST map `effort.opencode` to `reasoningEffort`, MUST pass `mode` and `color` through, and MUST omit unset optional fields.

#### Scenario: Effort null is omitted
GIVEN an OpenCode metadata JSON with `effort.opencode: null` and `color: "blue"`
WHEN `OpenCodeArtifactsAdministrator.render_artifacts([name], overrides={}, home=home)` is called
THEN the frontmatter includes `color: blue` and omits `reasoningEffort` rather than rendering YAML null.

### Requirement: OpenCode permission honors explicit override precedence
The system MUST emit raw `permission` exactly when present and otherwise derive permission from `AgentCaps`; empty derived permission MUST be omitted.

#### Scenario: Explicit permission wins over caps
GIVEN metadata for `change-orchestrator` with raw OpenCode `permission` and restrictive `caps`
WHEN `OpenCodeArtifactsAdministrator.render_artifacts(["change-orchestrator"], overrides={}, home=home)` is called
THEN the frontmatter contains the raw `permission` block exactly and does not render caps-derived permission.

#### Scenario: Caps derive deny permission
GIVEN metadata with `caps.write: false`, `caps.bash: false`, and `caps.spawn: ["change-explorer"]` and no raw `permission`
WHEN `OpenCodeArtifactsAdministrator.render_artifacts([name], overrides={}, home=home)` is called
THEN the frontmatter includes deny rules for edit, write, and bash, plus task allowlist entries for the allowed spawn target.
