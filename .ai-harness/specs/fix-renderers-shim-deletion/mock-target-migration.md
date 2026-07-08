# Spec — Mock target migration

Capability ID: `mock-target-migration`

Source of truth:
- `tests/test_renderers.py`
- `src/ai_harness/modules/harness/administrators/base.py`
- `src/ai_harness/modules/harness/administrators/claude.py`
- `src/ai_harness/modules/harness/administrators/opencode.py`
- `src/ai_harness/modules/harness/administrators/copilot.py`

## Purpose

Ensure monkeypatches and private-helper seams target the module that owns the behavior after the shim is deleted.

## Requirements

### Requirement: Shared helper monkeypatches target `administrators.base`
The system MUST target shared helper and resource monkeypatches at `ai_harness.modules.harness.administrators.base`.

#### Scenario: Resource traversal patch hits the owning module
GIVEN a test that patches resource traversal through `files` or `_AGENT_RESOURCE_DIRS`
WHEN the monkeypatch target is inspected
THEN it targets `ai_harness.modules.harness.administrators.base.files` or `ai_harness.modules.harness.administrators.base._AGENT_RESOURCE_DIRS`.

#### Scenario: Deleted shim target is rejected
GIVEN a test monkeypatch string under `ai_harness.modules.harness.renderers.*`
WHEN the test suite is reviewed for shim deletion readiness
THEN the change MUST be considered incomplete.

### Requirement: Provider-specific helper monkeypatches target provider modules
The system SHOULD patch provider-specific helper behavior in the provider module that owns it.

#### Scenario: Claude helper patch targets Claude administrator module
GIVEN a test that needs to patch Claude-only helper behavior such as `_claude_tools`
WHEN the patch target is selected
THEN it targets `ai_harness.modules.harness.administrators.claude`.

#### Scenario: OpenCode helper patch targets OpenCode administrator module
GIVEN a test that needs to patch OpenCode-only helper behavior such as `_opencode_permission`
WHEN the patch target is selected
THEN it targets `ai_harness.modules.harness.administrators.opencode`.

### Requirement: Deleted legacy APIs are not patched
The system MUST NOT preserve monkeypatches to shim-only APIs such as `get_agent_meta`, `render_agents`, or `RenderedFile`.

#### Scenario: Metadata tests use administrator metadata paths
GIVEN a test that needs metadata behavior after shim deletion
WHEN the test is migrated
THEN it patches or calls the actual administrator metadata path rather than `renderers.get_agent_meta`.

#### Scenario: Legacy shim API patch fails the migration
GIVEN a monkeypatch target containing `renderers.get_agent_meta`, `renderers.render_agents`, or `renderers.RenderedFile`
WHEN migration acceptance is evaluated
THEN the mock target MUST be removed or rewritten.

## Out of scope

- Adding new override-store persistence mocks belongs outside this child.
- Home isolation patching belongs to Child B.
- Prompt-content replacement belongs to Child C.
