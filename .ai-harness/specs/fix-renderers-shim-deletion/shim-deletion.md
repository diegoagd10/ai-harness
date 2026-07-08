# Spec — Shim deletion

Capability ID: `shim-deletion`

Source of truth:
- `src/ai_harness/modules/harness/renderers.py`
- `src/ai_harness/modules/harness/administrators/__init__.py`
- `src/ai_harness/modules/harness/operations.py`
- `src/ai_harness/modules/wizard/tui.py`

## Purpose

Remove the deprecated `ai_harness.modules.harness.renderers` compatibility module and prevent production runtime paths from depending on it.

## Requirements

### Requirement: Deleted compatibility shim
The system MUST NOT include `src/ai_harness/modules/harness/renderers.py` after this change.

#### Scenario: Shim file is absent
GIVEN the production source tree
WHEN the harness module directory is inspected
THEN `src/ai_harness/modules/harness/renderers.py` does not exist.

#### Scenario: Shim module cannot be treated as supported API
GIVEN code attempts to depend on `ai_harness.modules.harness.renderers`
WHEN the post-change package is evaluated
THEN the dependency is rejected as unsupported because the module has been removed.

### Requirement: No production imports of the deleted shim
The system MUST NOT import `ai_harness.modules.harness.renderers` from production code.

#### Scenario: Production code imports through administrators
GIVEN production files under `src/ai_harness`
WHEN import statements and import strings are inspected
THEN supported rendering and metadata references resolve through `ai_harness.modules.harness.administrators` or its owning submodules.

#### Scenario: Lingering production shim import fails acceptance
GIVEN any production file under `src/ai_harness`
WHEN it imports or dynamically references `ai_harness.modules.harness.renderers`
THEN the change MUST be considered incomplete.

## Out of scope

- Restoring a thin re-export shim is out of scope for this child.
- Home isolation failures belong to Child B.
- Prompt-content and install assertion redesign belongs to Child C.
