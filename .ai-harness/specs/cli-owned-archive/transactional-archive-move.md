# Spec — Transactional archive move

## Purpose

Move archive artifacts into the canonical top-level layout as an all-or-nothing filesystem operation with no duplicated specs directory.

## Requirements

### Requirement: Promote specs to top-level specs directory
The system MUST move `.ai-harness/changes/{change}/specs/` to `.ai-harness/specs/{change}/` on successful archive.

#### Scenario: Specs promoted
GIVEN `.ai-harness/changes/example/specs/` contains capability specs
WHEN `ai-harness change-archive example` succeeds
THEN those spec files exist under `.ai-harness/specs/example/`.

### Requirement: Move remaining Change to top-level archive directory
The system MUST move the remaining `.ai-harness/changes/{change}/` folder to `.ai-harness/archive/{change}/` on successful archive.

#### Scenario: Change planning artifacts archived
GIVEN `.ai-harness/changes/example/prd.md` exists
AND `.ai-harness/changes/example/design.md` exists
WHEN `ai-harness change-archive example` succeeds
THEN `.ai-harness/archive/example/prd.md` exists
AND `.ai-harness/archive/example/design.md` exists
AND `.ai-harness/changes/example/` no longer exists.

### Requirement: Avoid specs duplication in archived Change
The system MUST NOT leave a `specs/` directory under `.ai-harness/archive/{change}/` after successful archive.

#### Scenario: Archived Change excludes specs subtree
GIVEN `.ai-harness/changes/example/specs/archive-command.md` exists
WHEN `ai-harness change-archive example` succeeds
THEN `.ai-harness/specs/example/archive-command.md` exists
AND `.ai-harness/archive/example/specs/` does not exist.

### Requirement: Use canonical archive layout
The system MUST use `.ai-harness/specs/{change}/` and `.ai-harness/archive/{change}/` as archive destinations.

#### Scenario: Stale archive layout is not used
GIVEN a structurally valid Change named `example`
WHEN archive succeeds
THEN `.ai-harness/archive/example/` exists
AND `.ai-harness/changes/archive/example/` does not exist.

### Requirement: All-or-nothing move behavior
The system MUST roll back or stage filesystem moves so any move failure leaves the pre-archive filesystem state intact.

#### Scenario: Failure while moving remaining Change
GIVEN specs have started moving for `example`
AND moving the remaining Change folder fails
WHEN the archive operation handles the failure
THEN `.ai-harness/changes/example/` remains present with its `specs/` subtree
AND `.ai-harness/specs/example/` does not contain a partial promoted result
AND `.ai-harness/archive/example/` does not contain a partial archived result.

#### Scenario: Failure while promoting specs
GIVEN a structurally valid Change named `example`
AND the specs move fails because of a filesystem error
WHEN the archive operation handles the failure
THEN `.ai-harness/changes/example/specs/` remains present
AND `.ai-harness/specs/example/` is absent
AND `.ai-harness/archive/example/` is absent.
