# Spec — Ordered slice continuation

## Purpose

Continue delivery in authoritative PRD order after each validated capability checkpoint, then transition safely to final change validation and archive readiness.

## Requirements

### Requirement: Complete a slice only from current disk facts
The system MUST consider a capability complete only while its continuation approval matches current scope, its associated task set is non-empty and complete, and its non-empty slice validation remains present; completed capability IDs MUST be derived in PRD order and MUST NOT be persisted as lifecycle state.

#### Scenario: Continuation approval completes the current slice
GIVEN a reviewable selected capability and an unambiguous human approval at the pending continuation gate
WHEN `approve_pending_gate` atomically records the derived scope fingerprint and status is recomputed
THEN the capability appears in `completedCapabilities` and selection advances according to PRD order

#### Scenario: Ambiguous checkpoint response does not continue
GIVEN a selected capability is at `review-slice`
WHEN the human gives feedback, requests scope edits, or responds ambiguously
THEN no approval is recorded and planning for the next capability MUST NOT begin

### Requirement: Select and plan the next ordered slice
The system MUST select the first ordered capability without a valid continuation approval and MUST repeat its applicable `design` → `specs` → `tasks` → `implement` → `validate-slice` → `review-slice` routes without requiring artifacts for subsequent capabilities.

#### Scenario: Second slice starts after first approval
GIVEN a two-capability sliced change whose first capability is currently complete and whose second capability has no spec
WHEN status is recomputed
THEN the second capability is `currentCapability`, there is no later `nextCapability`, and the route is its required `design` or `specs` route

#### Scenario: Unrelated task completion does not advance the slice
GIVEN a later selected capability has pending associated tasks and all earlier or unrelated tasks are done
WHEN status is recomputed
THEN the route remains `implement` for the selected capability

### Requirement: End a one-capability change without inventing another slice
The system MUST route a sliced change with every capability currently complete to `final-validate` when root `validation.md` is absent or stale, and MUST NOT request a nonexistent next capability.

#### Scenario: One-capability terminal route
GIVEN a one-capability sliced change has valid continuation approval, complete associated tasks, and present slice validation but no root `validation.md`
WHEN status is derived
THEN `currentCapability` and `nextCapability` are null, the route is `final-validate`, and `nextRecommended` is `validate`

#### Scenario: Slice validation cannot stand in for final validation
GIVEN all capability validations are present and all continuation approvals are valid but root `validation.md` is missing
WHEN archive eligibility is evaluated
THEN the change is not archiveable and MUST route to final change validation

### Requirement: Require current final validation for archive routing
The system MUST route to `archive` only when every sliced capability remains complete and a non-empty root `validation.md` is newer than the latest continuation approval.

#### Scenario: Stale final validation is rejected
GIVEN every slice is complete but root `validation.md` predates the latest continuation approval
WHEN status is derived
THEN the route is `final-validate` and the stale final validation MUST NOT establish archive readiness

#### Scenario: Current final validation permits archive routing
GIVEN every slice is complete, every known task is done, and root `validation.md` is current
WHEN status is derived
THEN the route is `archive`

### Requirement: Preserve legacy routing semantics
The system MUST use legacy mode when `prd.md` has no `changeFlow` front matter, retain existing global artifact interpretation and route decisions, and MUST NOT infer sliced completion from missing slice metadata.

#### Scenario: Existing global-artifact change remains legacy
GIVEN an existing change has no `changeFlow` block and uses global spec, task, implementation, and validation artifacts
WHEN status is derived
THEN `sliceStatus.mode` is `legacy`, the route is `legacy`, and compatibility status fields preserve their prior meanings

#### Scenario: Legacy empty task store is not archive-ready by status
GIVEN a legacy change has root validation but its task store is empty
WHEN status is derived
THEN the existing non-empty-task route guard remains in effect and absent slice metadata MUST NOT imply completion

### Requirement: Keep archive preflight all-or-nothing
The system MUST recompute archive preconditions during a direct archive request and MUST reject the operation before any move if the change, readable task state, task completion, mode-specific slice completion, current final validation, or collision checks fail.

#### Scenario: Incomplete sliced task blocks every move
GIVEN status was previously observed at an archiveable route but an associated task is now incomplete
WHEN archive is invoked directly
THEN archive preflight fails, reports all detected preflight errors, and neither spec promotion nor change-folder movement occurs

#### Scenario: Missing final validation blocks legacy and sliced archive
GIVEN either a legacy or sliced change lacks root `validation.md`
WHEN archive is invoked
THEN the archive fails before any destination is modified

#### Scenario: Partial archive move is rolled back
GIVEN all preconditions pass but the second stage of the existing two-stage archive move fails
WHEN archive executes
THEN the first move is rolled back and the source change remains recoverable

### Requirement: Verify continuation without touching the user system
Automated verification MUST exercise lifecycle, archive, renderer, and CLI behavior in isolated temporary change folders, MUST NOT modify user-level state, and SHOULD use real pure collaborators while restricting mocks to HTTP clients, databases, or file-persistence boundaries.

#### Scenario: Supported toolchain runs focused coverage
GIVEN Python 3.12 or newer with `uv`, `ruff`, `pytest`, Typer/questionary seams, Docker/bash end-to-end support, and the pnpm/TypeScript renderer harness
WHEN the continuation contract is verified
THEN focused state, archive, compatibility, CLI, and exact OpenCode, Claude, and Copilot rendering tests pass without interacting with the user's change folders
