# Spec — Source-adjacent ASCII interaction diagrams

## Capability

Source-adjacent ASCII interaction diagrams — add compact source docstring diagrams beside the three owning seams required by the audit.

## Requirements

1. **R1: Administrator strategy diagram.** The codebase MUST include a compact plain-ASCII diagram near `ArtifactsAdministrator` and/or `ADMINISTRATORS` that shows callers dispatching through `ADMINISTRATORS` to provider administrator implementations.
2. **R2: Change/task FSM diagram.** The codebase MUST include a compact plain-ASCII diagram near `ChangeStatus` or `_derive_status()` in `src/ai_harness/modules/harness/change.py` that describes the file-backed change/task status FSM.
3. **R3: Wizard phase-loop diagram.** The codebase MUST include a compact plain-ASCII diagram near `_drive_phases()` in `src/ai_harness/modules/wizard/tui.py` that describes phase selection, phase execution, and navigation through the wizard loop.
4. **R4: Source adjacency.** Diagrams MUST live in source docstrings or immediately adjacent comments near the seams they explain, not in a new docs or ADR tree created solely for this cleanup.
5. **R5: Stable abstraction.** Diagrams SHOULD describe stable interactions and MUST NOT duplicate line-by-line implementation details, local variables, or transient control-flow minutiae.
6. **R6: Runtime neutrality.** Adding diagrams MUST NOT change runtime behavior, imports, or public APIs.

## Scenarios

### Scenario: Administrator strategy diagram is present near the administrator seam

GIVEN `src/ai_harness/modules/harness/administrators/base.py` or `src/ai_harness/modules/harness/administrators/__init__.py` after the change
WHEN the source near `ArtifactsAdministrator` or `ADMINISTRATORS` is searched for ASCII arrows or boxes
THEN at least one diagram block is present that describes caller to `ADMINISTRATORS` to provider dispatch.

### Scenario: Administrator diagram names the stable participants

GIVEN the administrator strategy diagram after the change
WHEN the diagram text is inspected
THEN it includes the stable participants `ADMINISTRATORS`, `ArtifactsAdministrator`, and concrete provider administrators or provider labels.

### Scenario: Change/task FSM diagram is present near status derivation

GIVEN `src/ai_harness/modules/harness/change.py` after the change
WHEN the source near `ChangeStatus` or `_derive_status()` is searched for ASCII arrows or boxes
THEN at least one diagram block is present that describes the change/task FSM.

### Scenario: Change/task FSM diagram names file-backed state

GIVEN the change/task FSM diagram after the change
WHEN the diagram text is inspected
THEN it references stable file-backed state concepts such as change status, tasks, or task status derivation.

### Scenario: Wizard phase-loop diagram is present near phase driver

GIVEN `src/ai_harness/modules/wizard/tui.py` after the change
WHEN the source near `_drive_phases()` is searched for ASCII arrows or boxes
THEN at least one diagram block is present that describes the wizard phase loop.

### Scenario: Wizard phase-loop diagram names navigation behavior

GIVEN the wizard phase-loop diagram after the change
WHEN the diagram text is inspected
THEN it includes stable phase-loop participants such as current phase, phase handler execution, navigation, or exit behavior.

### Scenario: No standalone docs tree is created for the diagrams

GIVEN the repository after the change
WHEN paths created by this capability are inspected
THEN no new docs or ADR tree exists solely to hold these three diagrams.

### Scenario: Diagrams are documentation-only

GIVEN the codebase after the diagrams are added
WHEN public APIs, imports, and runtime functions around the three seams are compared with their pre-diagram behavior
THEN no runtime behavior or public API changes are introduced by the diagram-only edits.

## Out of scope

- Do not create a new docs tree, ADR tree, or broad architecture documentation system for this cleanup.
- Do not add diagrams for override-store deep merge, install-plan writer dispatch, or any other seam beyond the three agreed diagrams.
- Do not rewrite protocols, state machines, wizard behavior, administrator dispatch, or runtime APIs while adding diagrams.
- Do not modify `e2e/`, `test-harness/`, `expected/`, README path references, `CODING_STANDARDS.md`, `AGENTS.md`, or `pyproject.toml` for this capability.
