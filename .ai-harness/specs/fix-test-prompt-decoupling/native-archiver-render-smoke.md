# Spec — Native archiver render smoke

## Purpose

Verify that the `change-archiver` change-agent renders on every native agent CLI through structural shape only, avoiding assertions about prompt text or archiver contract wording.

## Requirements

### Requirement: Render change-archiver across native CLIs
The system MUST provide `test_change_archiver_renders_on_native_agent_clis` parametrized across Claude, OpenCode, and Copilot.

#### Scenario: Claude renders archiver structurally
GIVEN `AgentCli.CLAUDE` and an isolated `tmp_path` home
WHEN the test renders `change-archiver` with `home=tmp_path` and `overrides={}`
THEN exactly one artifact is produced.

#### Scenario: OpenCode renders archiver structurally
GIVEN `AgentCli.OPENCODE` and an isolated `tmp_path` home
WHEN the test renders `change-archiver` with `home=tmp_path` and `overrides={}`
THEN exactly one artifact is produced.

#### Scenario: Copilot renders archiver structurally
GIVEN `AgentCli.COPILOT` and an isolated `tmp_path` home
WHEN the test renders `change-archiver` with `home=tmp_path` and `overrides={}`
THEN exactly one artifact is produced.

### Requirement: Assert only render structure
The system MUST assert frontmatter plus a non-empty rendered body and MUST NOT inspect archiver prompt prose.

#### Scenario: Rendered artifact has frontmatter and body
GIVEN a rendered `change-archiver` artifact
WHEN the test inspects its content
THEN the content starts with `---\n` and the body after frontmatter splitting is non-empty.

#### Scenario: Prompt wording changes do not break the smoke
GIVEN the `change-archiver` prompt body is editorially reworded while preserving renderability
WHEN the native archiver render smoke runs
THEN it does not fail because command text, archive contract wording, result envelope fields, or blocked-error prose changed.

### Requirement: Avoid user-system reads and mutations
The system MUST render with temporary homes and explicit empty overrides.

#### Scenario: User configuration is ignored
GIVEN a developer has local agent overrides in their real home directory
WHEN the smoke renders native CLI artifacts
THEN rendering uses `home=tmp_path` and `overrides={}` so user configuration does not affect the test.

#### Scenario: Test execution does not mutate the user's home
GIVEN the native render smoke is run on a developer workstation
WHEN artifacts are rendered
THEN any home-dependent operations are scoped to `tmp_path` rather than the user's actual home directory.
