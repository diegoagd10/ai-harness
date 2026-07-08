# Spec — Wizard assertion alignment

Capability ID: `wizard-assertion-alignment`

Source of truth:
- `tests/test_renderers.py`
- `tests/test_set_models.py`
- `src/ai_harness/modules/wizard/tui.py`
- `src/ai_harness/modules/harness/administrators/__init__.py`

## Purpose

Align wizard source-inspection assertions with the administrator import boundary so tests no longer require the deleted shim import line.

## Requirements

### Requirement: Source-inspection assertions expect administrator imports
The system MUST update wizard source-inspection assertions to require `ADMINISTRATORS` from `ai_harness.modules.harness.administrators`.

#### Scenario: Wizard import assertion accepts the modern boundary
GIVEN a test that inspects `src/ai_harness/modules/wizard/tui.py` source
WHEN it checks the `ADMINISTRATORS` import
THEN it expects the import to come from `ai_harness.modules.harness.administrators`.

#### Scenario: Wizard import assertion rejects the old shim boundary
GIVEN a test that inspects `src/ai_harness/modules/wizard/tui.py` source
WHEN it finds an expected import from `ai_harness.modules.harness.renderers`
THEN the assertion MUST be migrated because it is coupled to the deleted shim.

### Requirement: Source-inspection assertions avoid removed legacy calls
The system SHOULD assert that wizard code does not use removed legacy shim APIs where such source-inspection coverage already exists.

#### Scenario: Existing source inspection guards against legacy calls
GIVEN an existing wizard source-inspection test
WHEN it validates the migration boundary
THEN it may assert that removed APIs such as `render_agents` or `get_agent_meta` are not used by wizard code.

#### Scenario: Assertion alignment does not broaden test scope
GIVEN source-inspection tests near wizard behavior
WHEN they are updated for shim deletion
THEN they MUST NOT add Child B home-isolation checks or Child C prompt-content replacement assertions.

## Out of scope

- Home isolation assertions belong to Child B.
- Prompt-content and install body assertion replacement belongs to Child C.
