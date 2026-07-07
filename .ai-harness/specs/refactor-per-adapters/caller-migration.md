# Spec — Caller migration

## Purpose

Prove production callers, tests, and e2e expectations migrate in-place to the administrator seam, `Artifact.install_path`, and shared override-store helper while preserving installed paths.

## Requirements

### Requirement: Operations writes administrator artifacts
`operations.py` MUST select an administrator through `ADMINISTRATORS.get(cli)`, render artifacts through `render_artifacts(...)`, and write files using `home / artifact.install_path` and `artifact.content`.

#### Scenario: Install writes stable provider paths
GIVEN an install for Claude, OpenCode, and Copilot in a sandbox home
WHEN operations renders and writes change-agent artifacts
THEN the installed files appear at `.claude/skills/change-orchestrator/SKILL.md`, `.config/opencode/agent/<name>.md`, and `.copilot/agents/<name>.agent.md` with stable provider-visible paths.

#### Scenario: Generic CLI remains no-op
GIVEN install operations receive `AgentCli.GENERIC`
WHEN operations selects `ADMINISTRATORS.get(AgentCli.GENERIC)`
THEN no change-agent artifacts are rendered and no provider-specific branch is required.

### Requirement: Wizard uses administrator metadata and override-store helper
`wizard/tui.py` MUST query current metadata through provider administrators and MUST persist set-models choices through `save_override_store`; `wizard/pure.py` SHOULD remain pure while tests keep its agent vocabulary aligned with discovered templates.

#### Scenario: Set-models persists through shared helper
GIVEN the wizard user selects a new OpenCode model and effort for `change-explorer`
WHEN the confirm phase persists the choice
THEN `save_override_store(home, payload)` writes the override and a subsequent administrator render applies it when `overrides=None`.

#### Scenario: Wizard agent lists match discovered resources
GIVEN the pure wizard exposes Claude and OpenCode agent choices
WHEN tests compare those choices against administrator `discover_agent_names()` or the expected visible template set
THEN drift between wizard vocabulary, templates, and metadata resources is detected.

### Requirement: Tests and e2e migrate to public contracts
Tests MUST use `Artifact`, `ADMINISTRATORS[AgentCli.X].render_artifacts`, administrator metadata/discovery queries, and override-store helper functions instead of removed `RenderedFile`, `render_agents`, `get_agent_meta`, `write_override_store`, or private helper coupling where possible.

#### Scenario: E2E validates stable paths through new seam
GIVEN the e2e install flow runs in a fresh home
WHEN it installs and re-renders agents after overrides are saved
THEN path checks remain stable and override behavior is validated through administrator-rendered artifacts rather than old renderer APIs.
