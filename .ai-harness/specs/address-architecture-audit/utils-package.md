# Spec — Shared agent-set utilities package

## Capability

Shared agent-set utilities package — introduce `ai_harness.utils` as the stable home for selected cross-module pure agent-set helpers while keeping `wizard.pure` compatibility re-exports.

## Requirements

1. **R1: Utilities package.** `src/ai_harness/utils/__init__.py` MUST exist and re-export `AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, and `opencode_change_agents()`.
2. **R2: Focused implementation module.** `src/ai_harness/utils/agent_sets.py` MUST own the implementation of `AgentMode`, `parse_agent_mode()`, `claude_wizard_agents()`, and `opencode_change_agents()`.
3. **R3: Dependency boundary.** `ai_harness.utils.agent_sets` MUST NOT import wizard TUI modules, command modules, administrator modules, renderer modules, or other deep runtime seams that could create import cycles.
4. **R4: Wizard compatibility.** `src/ai_harness/modules/wizard/pure.py` MUST re-export the four migrated helper names for compatibility during this change, but MUST NOT own their implementation.
5. **R5: Production import migration.** Production callers identified by exploration, including `src/ai_harness/commands/set_models.py` and `src/ai_harness/modules/wizard/tui.py`, SHOULD import migrated helpers from `ai_harness.utils` where appropriate.
6. **R6: Test import migration.** Test callers identified by exploration, including `tests/test_set_models.py`, `tests/test_install.py`, and `tests/test_renderers.py`, SHOULD import migrated helpers from `ai_harness.utils` where appropriate.
7. **R7: Wizard seam preservation.** Wizard-internal helpers such as picker rows, model selections, picker builders, catalog joiners, label alignment, and override-payload builders MUST remain in `wizard.pure`.
8. **R8: No path configuration change.** This migration MUST NOT require a `pyproject.toml` change.

## Scenarios

### Scenario: Public utility imports are available

GIVEN the package after the change
WHEN a caller imports `AgentMode`, `parse_agent_mode`, `claude_wizard_agents`, and `opencode_change_agents` from `ai_harness.utils`
THEN the import succeeds without `ImportError`.

### Scenario: Utility import does not load wizard or administrator seams

GIVEN a fresh Python import process after the change
WHEN `ai_harness.utils` is imported
THEN wizard TUI, command, administrator, and renderer modules are not loaded as side effects.

### Scenario: Agent mode parsing behavior is preserved

GIVEN the migrated `parse_agent_mode()` from `ai_harness.utils`
WHEN it parses each previously supported mode string
THEN it returns the same `AgentMode` values as the previous `wizard.pure.parse_agent_mode()` implementation.

### Scenario: Claude wizard agent set behavior is preserved

GIVEN the migrated `claude_wizard_agents()` from `ai_harness.utils`
WHEN it is called with the same inputs used before the migration
THEN it returns the same agent-name set as the previous `wizard.pure` implementation.

### Scenario: OpenCode change agent set behavior is preserved

GIVEN the migrated `opencode_change_agents()` from `ai_harness.utils`
WHEN it is called with the same inputs used before the migration
THEN it returns the same agent-name set as the previous `wizard.pure` implementation.

### Scenario: Wizard pure compatibility re-export delegates to utils

GIVEN `src/ai_harness/modules/wizard/pure.py` after the change
WHEN a caller imports `parse_agent_mode` from `ai_harness.modules.wizard.pure`
THEN the imported callable is the same behavior as `ai_harness.utils.parse_agent_mode`.

### Scenario: Production set-models command imports from utils

GIVEN `src/ai_harness/commands/set_models.py` after the change
WHEN its imports are inspected
THEN `parse_agent_mode` is imported from `ai_harness.utils`, not from `ai_harness.modules.wizard.pure`.

### Scenario: Wizard-internal helpers stay in wizard pure

GIVEN `src/ai_harness/modules/wizard/pure.py` after the change
WHEN wizard-internal helper names such as `PickerRow`, `ModelSelection`, picker builders, catalog joiners, label alignment, and override-payload builders are imported from it
THEN those imports still succeed from `wizard.pure`.

### Scenario: Python path configuration remains unchanged

GIVEN `pyproject.toml` after the change
WHEN it is compared to the pre-change path configuration
THEN no new Python path configuration is required for importing `ai_harness.utils`.

## Out of scope

- Do not migrate wizard-internal picker, catalog, label, or override-payload helpers into `utils/`.
- Do not remove `wizard.pure` compatibility re-exports during this change.
- Do not broaden `utils/` into a junk drawer for unrelated helpers.
- Do not modify `e2e/`, `test-harness/`, `expected/`, README path references, `CODING_STANDARDS.md`, `AGENTS.md`, or `pyproject.toml` unless an unexpected import-path failure proves it necessary.
