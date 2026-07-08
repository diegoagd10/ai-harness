# Spec — Regression gate clarity

## Purpose

Make validation expectations explicit so the test-side decoupling is proven by targeted pytest runs, the full suite, and ruff gates.

## Requirements

### Requirement: Targeted pytest gates pass
The system MUST pass targeted pytest gates for the renderer and install test surfaces touched by this change.

#### Scenario: Renderer tests validate removed and new smoke coverage
GIVEN the prompt-coupled renderer tests have been removed and smoke tests have been added or reshaped
WHEN `uv run pytest tests/test_renderers.py` is executed
THEN the command passes.

#### Scenario: Install tests validate body containment
GIVEN the Claude install body assertion has been relaxed to containment
WHEN `uv run pytest tests/test_install.py` is executed
THEN the command passes.

### Requirement: Final regression gates pass
The system MUST pass the full pytest suite and ruff format/check gates.

#### Scenario: Full pytest suite passes
GIVEN the test-side changes are complete
WHEN `uv run pytest` is executed
THEN the command passes without failures.

#### Scenario: Ruff format check passes
GIVEN imports and formatting may have changed after deleting tests
WHEN `uv run ruff format --check .` is executed
THEN the command passes.

#### Scenario: Ruff lint check passes
GIVEN deleted prompt tests may leave unused imports or stale code paths
WHEN `uv run ruff check .` is executed
THEN the command passes.
