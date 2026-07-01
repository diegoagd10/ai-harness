# Spec — skip-when-init-block-present

## Purpose

When an agent doc already carries the new
`<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->` markers,
`init_repo` MUST leave it byte-identical: no rewrite, no append, no mtime
change. The doc is still recorded in `InitResult.init_block_targets` so
the CLI can echo "already present — unchanged", but
`InitResult.wrote_init_block` MUST remain `False` for that file's
contribution.

This is the kept-unchanged branch of the four-case decision table —
the idempotency contract.

## Non-goals

- No touching of the new init block's body content (it is the block we
  just owned).
- No marking of "kept" files as freshly written — the
  `wrote_init_block` flag stays `False` for a file that was already at
  the new markers.
- No behaviour change for legacy-marker files that happen to also include
  the new markers — see Risks in the PRD.

## Requirements

### Requirement: file not modified when new markers present

When an existing agent doc already contains both
`<!-- ai-harness:init:start -->` and `<!-- ai-harness:init:end -->`, the
system MUST NOT modify the file's bytes or its mtime.

#### Scenario: idempotent re-run on a file with new markers
GIVEN a `CLAUDE.md` containing the new init managed block plus optional
user content above and below
WHEN `init_repo` is invoked
THEN the file's bytes are unchanged (eq to the pre-call bytes)
AND the file's mtime is unchanged
AND the file appears in `InitResult.init_block_targets`
AND `InitResult.wrote_init_block` is `False`.

### Requirement: both files at new markers yields an empty write

When both `CLAUDE.md` and `AGENTS.md` already carry the new init
markers, the system MUST make no writes to either file and MUST set
`InitResult.wrote_init_block` to `False`.

#### Scenario: nothing-to-do on a saturated repo
GIVEN a repo root where both `CLAUDE.md` and `AGENTS.md` exist and
both contain the new init managed block with no user edits
WHEN `init_repo` is invoked
THEN neither file is rewritten
AND `InitResult.init_block_targets == ()`
AND `InitResult.wrote_init_block is False`.

### Requirement: one kept, one needs work

When one agent doc already carries the new init markers and the other
has none, the system MUST keep the marked one untouched and apply the
appropriate action (create or append) to the unmarked one.

#### Scenario: CLAUDE.md kept, AGENTS.md appended
GIVEN a `CLAUDE.md` that contains the new init managed block (and only
that) and an `AGENTS.md` that exists with user content but no markers
WHEN `init_repo` is invoked
THEN `CLAUDE.md` is byte-identical to its pre-call contents
AND `AGENTS.md` ends with the new init managed block appended after
its existing content
AND `InitResult.init_block_targets == ("CLAUDE.md", "AGENTS.md")`
AND `InitResult.wrote_init_block is True` (because `AGENTS.md` was
modified).

## End-to-end coverage

The mtime / no-rewrite invariant is best verified against a real
disk: it is the difference between "the file's contents are
unchanged" (which a unit test can prove in memory) and "the file was
not even rewritten" (which requires `stat` against the live
filesystem). The e2e tier in `cover-init-with-e2e.md` — specifically
the *idempotent re-run on a saturated repo is a no-op* requirement —
records the `stat -c %Y` mtimes of all three artifacts in a seeded
saturated temp dir, invokes `ai-harness init`, and asserts the
mtimes are unchanged and the CLI reports an "already present /
unchanged" indicator for each. The same requirement proves the
exit-code-zero guarantee on the no-op path, complementing the
unit-level `wrote_init_block is False` flag.
