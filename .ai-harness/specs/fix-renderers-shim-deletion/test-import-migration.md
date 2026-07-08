# Spec — Test import migration

Capability ID: `test-import-migration`

Source of truth:
- `tests/test_renderers.py`
- `tests/test_install.py`
- `src/ai_harness/modules/harness/administrators/__init__.py`
- `src/ai_harness/modules/harness/administrators/base.py`

## Purpose

Ensure renderer and install tests collect against the modern administrator package rather than the deleted `renderers` shim.

## Requirements

### Requirement: Public test imports use the administrator package
The system MUST import public administrator API names in tests from `ai_harness.modules.harness.administrators`.

#### Scenario: Renderer tests collect with administrator public imports
GIVEN `tests/test_renderers.py`
WHEN pytest collects the module
THEN public names such as `ADMINISTRATORS`, `AgentCaps`, `AgentMetadata`, `Artifact`, concrete administrators, `discover_agent_names`, and `load_agent_metadata` are imported from `ai_harness.modules.harness.administrators`.

#### Scenario: Renderer tests do not collect through the deleted shim
GIVEN `tests/test_renderers.py`
WHEN its imports are inspected
THEN it MUST NOT import public names from `ai_harness.modules.harness.renderers`.

### Requirement: Install tests use administrator imports
The system MUST migrate `tests/test_install.py` top-level rendering and metadata imports to `ai_harness.modules.harness.administrators`.

#### Scenario: Install tests collect after shim deletion
GIVEN `tests/test_install.py`
WHEN pytest collects the module after `renderers.py` is removed
THEN imports such as `ADMINISTRATORS`, `AgentCaps`, and `discover_agent_names` resolve from `ai_harness.modules.harness.administrators`.

#### Scenario: Install tests reject shim imports
GIVEN `tests/test_install.py`
WHEN its top-level imports are inspected
THEN it MUST NOT import from `ai_harness.modules.harness.renderers`.

### Requirement: Existing private helper tests target the owning shared module
The system SHOULD keep existing private shared-helper tests pointed at `ai_harness.modules.harness.administrators.base` without expanding private-helper coverage.

#### Scenario: Shared helper tests use base module imports
GIVEN existing tests for shared helper behavior such as metadata schema decoding or resource traversal
WHEN those tests import private helper seams
THEN they import from `ai_harness.modules.harness.administrators.base`.

#### Scenario: Migration does not create new private API expectations
GIVEN the shim deletion migration
WHEN helper tests are updated
THEN they SHOULD preserve existing behavioral coverage without adding new private-helper assertions unrelated to removing the shim.

## Out of scope

- Rewriting tests for home directory isolation belongs to Child B.
- Replacing prompt-content tests or install body exact assertions belongs to Child C.
