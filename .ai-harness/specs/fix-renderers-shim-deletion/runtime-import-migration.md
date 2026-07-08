# Spec — Runtime administrator import migration

Capability ID: `runtime-import-migration`

Source of truth:
- `src/ai_harness/modules/wizard/tui.py`
- `src/ai_harness/modules/harness/administrators/__init__.py`

## Purpose

Ensure wizard runtime code resolves `ADMINISTRATORS` through the modern administrator package, not the deleted compatibility shim.

## Requirements

### Requirement: Wizard imports administrator dispatch from the administrator package
The system MUST import `ADMINISTRATORS` in `wizard/tui.py` from `ai_harness.modules.harness.administrators`.

#### Scenario: Wizard source uses the modern administrator import
GIVEN the `src/ai_harness/modules/wizard/tui.py` source file
WHEN the runtime import boundary is inspected
THEN it contains an import of `ADMINISTRATORS` from `ai_harness.modules.harness.administrators`.

#### Scenario: Wizard source keeps the deleted shim out of runtime imports
GIVEN the `src/ai_harness/modules/wizard/tui.py` source file
WHEN the runtime import boundary is inspected
THEN it MUST NOT import `ADMINISTRATORS` from `ai_harness.modules.harness.renderers`.

### Requirement: Wizard behavior remains routed through administrator metadata
The system SHOULD continue to use the administrator dispatch table for install and set-models wizard flows without adding provider-specific branching in `wizard/tui.py`.

#### Scenario: Wizard asks the administrator table for provider behavior
GIVEN a wizard flow that needs provider metadata or rendering behavior
WHEN it selects an administrator for a supported `AgentCli`
THEN the selection comes from `ADMINISTRATORS` exposed by `ai_harness.modules.harness.administrators`.

#### Scenario: Wizard does not compensate for shim deletion with provider branches
GIVEN the shim has been deleted
WHEN `wizard/tui.py` is inspected for provider-specific fallback logic
THEN it MUST NOT introduce direct branches over Claude, OpenCode, or Copilot rendering internals to replace the administrator package seam.

## Out of scope

- Home isolation for wizard/render tests belongs to Child B.
- Prompt-content or install body assertion replacement belongs to Child C.
