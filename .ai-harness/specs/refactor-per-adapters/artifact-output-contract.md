# Spec — Artifact output contract

## Purpose

Prove renderer output is expressed as the design's frozen `Artifact(install_path, content)` dataclass and that callers can write artifacts without knowing provider layouts. This replaces the old `RenderedFile(filename, content)` abstraction.

## Requirements

### Requirement: Administrators return Artifact values
Every administrator MUST return `Artifact` objects with `install_path` and `content`, and MUST NOT require callers to unpack tuples or read a `filename` field.

#### Scenario: Rendered result exposes install_path and content
GIVEN any supported administrator and a valid agent name
WHEN `render_artifacts([name], overrides={}, home=home)` is called
THEN each result is an `Artifact` with a home-relative POSIX `install_path` and full file `content`.

### Requirement: install_path is home-relative and provider-owned
The system MUST make `install_path` a provider-owned, home-relative POSIX path suitable for `home / artifact.install_path` writes.

#### Scenario: Operations can write without provider path logic
GIVEN artifacts returned for Claude, OpenCode, and Copilot
WHEN install operations write each artifact to `home / artifact.install_path`
THEN files land in `.claude/...`, `.config/opencode/...`, and `.copilot/...` paths without operations assembling provider-specific filenames.

### Requirement: Artifact replaces RenderedFile in acceptance surfaces
Tests and production callers SHOULD assert and consume the `Artifact` contract instead of the removed `RenderedFile` or private renderer helper outputs.

#### Scenario: Tests compare Artifact objects directly
GIVEN an expected rendered result
WHEN tests assert administrator behavior
THEN they compare `Artifact(install_path=..., content=...)` or its named fields rather than tuple positions or `filename`.
