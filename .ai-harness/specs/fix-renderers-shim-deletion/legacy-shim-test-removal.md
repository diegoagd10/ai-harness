# Spec — Legacy shim test removal

Capability ID: `legacy-shim-test-removal`

Source of truth:
- `tests/test_renderers.py`
- `src/ai_harness/modules/harness/administrators/__init__.py`

## Purpose

Remove tests whose only subject is the deleted compatibility shim instead of replacing them with new shim-coupled assertions.

## Requirements

### Requirement: Remove public-surface tests for `renderers.__all__`
The system MUST remove the shim-specific public-surface tests named `test_renderers_public_surface_excludes_old_apis` and `test_renderers_public_surface_includes_new_apis`.

#### Scenario: Shim public-surface tests are absent
GIVEN `tests/test_renderers.py`
WHEN test function names are inspected
THEN `test_renderers_public_surface_excludes_old_apis` and `test_renderers_public_surface_includes_new_apis` are not present.

#### Scenario: Shim `__all__` assertion is not recreated
GIVEN the deleted `renderers` module
WHEN tests are migrated
THEN no new assertion depends on `renderers.__all__` or an equivalent compatibility-shim public surface.

### Requirement: Remove `render_agents` byte-parity tests
The system MUST remove the Claude, OpenCode, and Copilot `render_agents` parity tests whose purpose is comparing the shim to administrator rendering.

#### Scenario: Provider parity tests tied to `render_agents` are absent
GIVEN `tests/test_renderers.py`
WHEN tests are inspected for legacy parity coverage
THEN the Claude, OpenCode, and Copilot byte-compatibility tests against `render_agents` are removed.

#### Scenario: Administrator behavior tests remain independent of the shim
GIVEN behavior tests that verify rendered artifacts or metadata
WHEN the shim-specific parity tests are deleted
THEN remaining tests MAY continue to assert administrator behavior directly, but MUST NOT compare against `renderers.render_agents`.

## Out of scope

- Deleting prompt-content tests belongs to Child C.
- Changing render call home or override semantics belongs to Child B.
