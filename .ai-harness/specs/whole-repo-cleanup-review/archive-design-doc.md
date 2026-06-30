# Spec — archive-design-doc

## Purpose

Relocate `docs/design/change-orchestrator.md` into
`.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
so durable design narrative travels with the change archive it documents, and
so the active `docs/design/` surface shrinks by one file. The move MUST be
byte-identical and MUST preserve commit history.

## Requirements

### Requirement: the destination file exists at the archive target

The system MUST create
`.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
at HEAD such that the file is reachable from the working tree.

#### Scenario: archive target contains the relocated doc

GIVEN `.ai-harness/changes/archive/borrow-gentle-orchestrator/` exists
(broken-gentle archive folder, already populated with `design.md`,
`exploration.md`, `prd.md`, etc.)
AND `docs/design/change-orchestrator.md` exists at pre-archive HEAD
WHEN the cleanup is applied
THEN
`.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
exists at HEAD and is a regular file (non-empty).

### Requirement: the source path no longer exists

The system MUST remove `docs/design/change-orchestrator.md` from the working
tree at HEAD so no active copy remains in `docs/design/`.

#### Scenario: source path absent at HEAD

GIVEN the archive folder already has the relocated doc at the new path
WHEN the cleanup is applied
THEN `docs/design/change-orchestrator.md` does not exist at HEAD
AND a directory listing of `docs/design/` no longer includes
`change-orchestrator.md`.

### Requirement: byte-identical content

The system MUST move the file without changing its bytes. The SHA-256 of the
new path at HEAD MUST equal the SHA-256 of the old path at the parent commit
(`HEAD^`).

#### Scenario: pre-move SHA equals post-move SHA

GIVEN `SRC_SHA = sha256sum(HEAD^:docs/design/change-orchestrator.md)` recorded
before cleanup
WHEN the cleanup commit is applied
THEN
`sha256sum(HEAD:.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md)`
equals `SRC_SHA`.

#### Scenario: no in-flight edits are bundled with the move

GIVEN the cleanup is committed
WHEN the diff for the move commit is inspected
THEN the diff contains only a rename hunk
(git rename detection ≥ 90% similarity)
AND zero content-changing lines exist in the moved file's diff.

### Requirement: history-following via git rename detection

The system MUST use `git mv` (or an equivalent rename-preserving move) so
that the relocated file's commit history is reachable via
`git log --follow`.

#### Scenario: git log --follow returns prior commits

GIVEN the cleanup commit is applied
WHEN `git log --follow
.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
is run
THEN the output includes at least one commit prior to the cleanup commit
with the old path `docs/design/change-orchestrator.md` as the source of a
rename.
AND the commit count returned is greater than or equal to the commit count
returned by
`git log --follow docs/design/change-orchestrator.md@{pre-cleanup}`.

### Requirement: cross-references inside the archive are self-consistent

The system SHOULD update any cross-reference inside the
`borrow-gentle-orchestrator/` archive that links to the old
`docs/design/change-orchestrator.md` path so the archive stays
self-consistent. The move itself MUST NOT introduce edits to any file
outside the affected pair except where needed to fix such stale paths.

#### Scenario: archive-internal citations point at the new path

GIVEN the archive folder holds evidence notes (`exploration.md`,
`validation.md`, `implementation.md`, `specs/*.md`, `tasks.json`, etc.)
THEN at HEAD, every occurrence of the literal string
`docs/design/change-orchestrator.md` inside
`.ai-harness/changes/archive/borrow-gentle-orchestrator/**` that represents an
active cross-reference (not historical evidence) is rewritten to the new
path `.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`.
AND any occurrence preserved as historical evidence is annotated or scoped so
it is not mistaken for a live link by future readers.

### Requirement: no collateral damage in `docs/design/`

The system MUST NOT add, remove, rename, or modify any file under
`docs/design/` other than the single removal of
`change-orchestrator.md`.

#### Scenario: only one file in `docs/design/` is touched

GIVEN the cleanup is applied
WHEN the diff for the move-only commit is inspected
THEN `docs/design/` shows exactly one affected file: the renamed
`change-orchestrator.md`.
AND no other entry under `docs/design/` appears in the diff.
