# Spec — Regression-gate clarity

## Purpose

Define the focused validation gates that prove the migration preserved renderer behavior and removed ambient-home sensitivity.

## Requirements

### Requirement: Targeted renderer pytest passes
The system MUST pass the renderer test module after the isolation migration.

#### Scenario: Full renderer module passes
GIVEN the migration has updated direct calls, helper call chains, and override-store tests
WHEN `uv run pytest tests/test_renderers.py` is executed
THEN the command exits successfully.

#### Scenario: Helper signature miss fails visibly
GIVEN a helper caller was not updated to pass `tmp_path`
WHEN `uv run pytest tests/test_renderers.py` is executed
THEN pytest fails with an explicit call/signature error rather than silently reading real `HOME`.

### Requirement: Narrow override-store gate passes
The system SHOULD pass a targeted pytest selection covering override-store and no-overrides behavior.

#### Scenario: Override-store focused selection passes
GIVEN disk-store semantics were preserved with `home=tmp_path`
WHEN `uv run pytest tests/test_renderers.py -k "override_store or no_overrides or render_agents"` is executed
THEN the command exits successfully.

#### Scenario: Incorrect overrides replacement is caught
GIVEN an override-store test was changed from omitted/`None` overrides to `overrides={}`
WHEN the focused selection runs
THEN the affected disk-read assertion fails or the audit rejects the migration.

### Requirement: Ruff gates pass for the edited file
The system MUST keep the edited test file formatted and lint-clean.

#### Scenario: Format check passes
GIVEN `tmp_path: Path` parameters and call arguments were added
WHEN `uv run ruff format --check tests/test_renderers.py` is executed
THEN the command exits successfully.

#### Scenario: Lint check passes
GIVEN the migration changed signatures and call expressions only
WHEN `uv run ruff check tests/test_renderers.py` is executed
THEN the command exits successfully without unused imports or style violations.

### Requirement: Full pytest does not regress
The system MUST NOT introduce regressions outside `tests/test_renderers.py`.

#### Scenario: Full suite remains green
GIVEN the targeted renderer and ruff gates pass
WHEN full pytest is executed for the repository
THEN the suite does not fail because of this migration.

#### Scenario: Child C scope is not required for this gate
GIVEN prompt-content deletions, install verbatim rewrites, and replacement smoke checks belong to Child C
WHEN this Change is validated
THEN failures requiring those out-of-scope edits are not solved by expanding this Change.
