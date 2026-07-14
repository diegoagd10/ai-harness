# Spec — Safe normal-risk first slice

## Purpose

Deliver the first ordered, normal-risk capability as an independently useful slice while deriving identity, readiness, and routing from durable change artifacts rather than mutable lifecycle state.

## Requirements

### Requirement: Select the first capability from versioned PRD metadata
The system MUST select the first capability in valid `changeFlow` front matter whose continuation approval is absent or invalid, using its stable kebab-case ID and one-based PRD order without inferring identity or order from prose, filenames, or a persisted current-capability pointer.

#### Scenario: First slice is selected
GIVEN a sliced PRD with two valid, ordered capabilities and neither capability has a continuation approval
WHEN change status is derived
THEN `sliceStatus.currentCapability` identifies the first capability, `nextCapability` identifies the second capability, and the route concerns only the first capability

#### Scenario: Future slices are not prerequisites
GIVEN the first capability has the artifacts required for its current route and later capabilities have no designs, specs, validations, or associated tasks
WHEN change status is derived
THEN the first capability MAY advance independently and the absent future artifacts MUST NOT block it

### Requirement: Apply deterministic slice artifact paths
The system MUST use `designs/<capability-id>.md` for a normal-risk slice design, `specs/<capability-id>.md` for its spec, and `validations/<capability-id>.md` for its slice validation; each required sliced artifact MUST be a regular, non-empty file written atomically.

#### Scenario: Optional design is omitted
GIVEN the selected normal-risk capability declares `design: none` and has no slice design
WHEN its route is derived
THEN the system routes directly to `specs` and reports `specs/<capability-id>.md` as `specPath`

#### Scenario: Slice design is required
GIVEN the selected normal-risk capability declares `design: slice` and its slice design is missing or empty
WHEN its route is derived
THEN the system routes to `design` with `designPath` equal to `designs/<capability-id>.md` and MUST NOT treat the capability as designed

#### Scenario: Empty spec is not complete
GIVEN the selected capability's spec path exists as an empty file or is not a regular file
WHEN its route is derived
THEN the system routes to `specs` with an actionable diagnostic and MUST NOT advance to task planning

### Requirement: Require a non-empty associated task set
The system MUST derive selected-slice task state from the cumulative `tasks.json` store and associate only tasks whose `Task.spec` canonicalizes to `specs/<capability-id>.md`; zero associated tasks MUST route to `tasks`.

#### Scenario: Canonical and legacy task references associate
GIVEN tasks reference the selected capability as `<id>`, `<id>.md`, or `specs/<id>.md`
WHEN capability task state is derived
THEN each reference associates with `specs/<id>.md` and the tasks remain in their existing order

#### Scenario: Missing or empty task input is safe
GIVEN `tasks.json` is missing, malformed, empty, or contains no task associated with the selected spec
WHEN change status is derived
THEN the capability MUST NOT be complete, the route MUST NOT advance beyond task planning, and the status provides an actionable reason

#### Scenario: Unsafe references do not associate
GIVEN a task uses an absolute path, parent traversal, nested spec path, empty capability ID, or a different capability's spec
WHEN selected-slice task state is derived
THEN that task does not associate and the system reports a safe routing diagnostic rather than crediting it to the selected capability

### Requirement: Route one normal-risk slice through delivery and validation
The system MUST route a normal-risk selected capability from non-empty associated tasks to `implement` while any associated task is pending, then to `validate-slice` when all associated tasks are done, and then to `review-slice` only when a non-empty, current slice validation exists.

#### Scenario: Pending selected task requires implementation
GIVEN the selected capability has a valid spec and a non-empty associated task set containing a pending task
WHEN change status is derived
THEN the route is `implement` even if every unrelated task is complete

#### Scenario: Completed selected tasks require slice validation
GIVEN every task associated with the selected capability is done and its slice validation is missing or empty
WHEN change status is derived
THEN the route is `validate-slice` and `validationPath` is `validations/<capability-id>.md`

#### Scenario: Stale initial validation is regenerated
GIVEN the selected capability has not yet received continuation approval and its validation is older than its current PRD, applicable design, spec, or associated task input
WHEN change status is derived
THEN the route is `validate-slice` and the stale validation MUST NOT make the slice reviewable

#### Scenario: Validated normal-risk slice reaches one checkpoint
GIVEN all selected tasks are done and a non-empty current slice validation exists
WHEN change status is derived
THEN the route is `review-slice`, `approval.gate` is `continuation`, and later capability planning MUST wait for explicit acknowledgment

### Requirement: Preserve compatibility projections
The system MUST expose sliced routing in additive schema-version-3 `sliceStatus` while preserving every existing status field name and type and projecting only existing tokens through `nextRecommended`.

#### Scenario: Rich routes are projected safely
GIVEN status derives `validate-slice`, `review-slice`, or malformed-state routing
WHEN status is serialized
THEN `validate-slice` projects to `validate`, human gates and blockers project to `resolve-blockers`, and no legacy consumer receives a new route token

#### Scenario: Human gate has no phase config context
GIVEN the selected slice is at `review-slice`
WHEN status is serialized
THEN `sliceStatus.route` remains authoritative, `blockedReasons` explains the required decision, and `configContext` is null
