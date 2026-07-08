# Spec — Documentation cleanup

Capability ID: `documentation-cleanup`

Source of truth:
- `README.md`
- `src/ai_harness/modules/harness/operations.py`
- `src/ai_harness/modules/harness/override_store.py`
- `src/ai_harness/modules/harness/administrators/base.py`
- `src/ai_harness/modules/harness/administrators/`

## Purpose

Keep README, docstrings, and comments aligned with the administrator package as the rendering and metadata home.

## Requirements

### Requirement: Documentation names administrators as the rendering home
The system MUST describe `src/ai_harness/modules/harness/administrators/` as the rendering and metadata boundary where architecture prose names the rendering subsystem.

#### Scenario: README points to the administrator package
GIVEN `README.md`
WHEN architecture documentation describes administrator rendering or metadata dispatch
THEN it points readers to `src/ai_harness/modules/harness/administrators/` instead of `renderers.py`.

#### Scenario: README does not advertise the deleted shim
GIVEN `README.md`
WHEN the document is searched for the deleted rendering home
THEN it MUST NOT direct readers to `src/ai_harness/modules/harness/renderers.py` as supported architecture.

### Requirement: Source prose avoids stale shim references
The system SHOULD update docstrings and comments in production files so they do not describe helper ownership as living in `renderers.py`.

#### Scenario: Operations prose reflects administrator ownership
GIVEN `src/ai_harness/modules/harness/operations.py`
WHEN rendering architecture prose is inspected
THEN it describes provider-specific rendering through the administrator package.

#### Scenario: Helper-location comments do not point to the shim
GIVEN `src/ai_harness/modules/harness/override_store.py` and `src/ai_harness/modules/harness/administrators/base.py`
WHEN docstrings and comments are inspected
THEN they MUST NOT identify private helpers as living in the deleted `renderers.py` shim.

## Out of scope

- Broad README restructuring is out of scope.
- Child B owns home-isolation documentation if any is needed.
- Child C owns prompt/resource smoke-check documentation if any is needed.
