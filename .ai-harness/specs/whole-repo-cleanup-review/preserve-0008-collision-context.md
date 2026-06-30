# Spec — preserve-0008-collision-context

## Purpose

Negative-assertion guard scoped to the known 0008 numbering collision. Both
`0008-worktree-current-branch-and-delete.md` and
`0008-copilot-loop-agents-native-model.md` are active, both have live
references, and the collision is explicitly deferred to a separate,
evidence-backed follow-up Change. This cleanup MUST NOT rename, renumber,
delete, or otherwise alter either 0008 file.

## Requirements

### Requirement: the worktree 0008 is unchanged

The system MUST NOT modify, rename, renumber, or delete
`docs/adr/0008-worktree-current-branch-and-delete.md`.

#### Scenario: worktree 0008 SHA is invariant

GIVEN
`SRC_SHA = sha256sum(HEAD^:docs/adr/0008-worktree-current-branch-and-delete.md)`
recorded before cleanup
WHEN the cleanup commit is applied
THEN
`sha256sum(HEAD:docs/adr/0008-worktree-current-branch-and-delete.md) == SRC_SHA`.

#### Scenario: worktree 0008 is not in the cleanup diff

GIVEN the cleanup commit is applied
WHEN the diff for the commit is inspected
THEN no path matching
`^docs/adr/0008-worktree-current-branch-and-delete\.md$` appears in the
diff (zero additions, zero removals, zero modifications).

### Requirement: the copilot-loop 0008 is unchanged

The system MUST NOT modify, rename, renumber, or delete
`docs/adr/0008-copilot-loop-agents-native-model.md`.

#### Scenario: copilot-loop 0008 SHA is invariant

GIVEN
`SRC_SHA = sha256sum(HEAD^:docs/adr/0008-copilot-loop-agents-native-model.md)`
recorded before cleanup
WHEN the cleanup commit is applied
THEN
`sha256sum(HEAD:docs/adr/0008-copilot-loop-agents-native-model.md) == SRC_SHA`.

#### Scenario: copilot-loop 0008 is not in the cleanup diff

GIVEN the cleanup commit is applied
WHEN the diff for the commit is inspected
THEN no path matching
`^docs/adr/0008-copilot-loop-agents-native-model\.md$` appears in the
diff.

### Requirement: the collision is not silently resolved

The system MUST NOT bundle resolution of the 0008 numbering collision into
this Change. Resolving the collision (renumbering one to 0015 or
consolidating) is out of scope and requires its own evidence-backed
follow-up. The collision MUST persist at HEAD.

#### Scenario: both 0008 paths still exist at HEAD

GIVEN the cleanup commit is applied
WHEN a directory listing of `docs/adr/` is taken at HEAD
THEN both
`0008-worktree-current-branch-and-delete.md` and
`0008-copilot-loop-agents-native-model.md` exist as distinct files.
AND both filenames still begin with `0008-` (no renumber has happened).

#### Scenario: collision-context references remain valid

GIVEN ADR `0009-worktree-create-subcommand.md` references the worktree 0008
AND `README.md` references the copilot-loop 0008 by its full filename
WHEN the cleanup is applied
THEN both references continue to resolve to existing files at HEAD
AND the references are byte-identical to their pre-cleanup form (no
silent rewrite to a renamed path).

### Requirement: the deferred-collision note is preserved

The system SHOULD leave a one-line note in this Change's Risks section
flagging the collision as a deferred follow-up, so it remains visible
to future explorers loading this archive.

#### Scenario: the Risks section cites the deferred follow-up

GIVEN the cleanup Change is archived at
`.ai-harness/changes/archive/whole-repo-cleanup-review/`
WHEN the archived `prd.md` (or its successor file) is read
THEN the Risks section contains a one-line flag for the ADR 0008
numbering collision naming both files and stating the resolution is
deferred to a follow-up Change.
