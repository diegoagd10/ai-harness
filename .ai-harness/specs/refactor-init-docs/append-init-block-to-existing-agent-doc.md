# Spec — append-init-block-to-existing-agent-doc

## Purpose

For an existing agent doc (`CLAUDE.md` or `AGENTS.md`) that contains **no**
`ai-harness` markers at all, `init_repo` appends the new init managed block
with a leading blank line, without touching any other content. The user's
own notes above the block survive byte-identical.

This is the bare-append branch of the four-case decision table — the case
where the file exists but carries no legacy or new markers.

## Non-goals

- No rewrite when the file already carries the new init markers (covered by
  `skip-when-init-block-present`).
- No rewrite with legacy `ai-harness:start/end` markers (covered by
  `migrate-legacy-agent-doc-block`).
- No formatting changes inside the user's content (no normalisation of
  line endings, no whitespace collapsing, no trailing-newline removal).

## Requirements

### Requirement: append when no markers present

When an agent doc exists and contains neither `<!-- ai-harness:init:start -->`
nor `<!-- ai-harness:start -->`, the system MUST append the new init
managed block to that file and MUST set `InitResult.wrote_init_block` to
`True`.

#### Scenario: populated file receives the block
GIVEN an existing `CLAUDE.md` containing only human-authored content and
no `ai-harness` markers
WHEN `init_repo` is invoked
THEN the file ends with the new init managed block
AND every byte of the original content survives unchanged
AND the file appears in `InitResult.init_block_targets`.

### Requirement: leading blank line

The append path MUST ensure a blank line separates the user's last line
from the new init block's start marker, so the marker never collides with
user content.

#### Scenario: separator between user content and block
GIVEN an existing `CLAUDE.md` whose last line is non-empty (with or
without a trailing newline)
WHEN `init_repo` is invoked
THEN the line immediately preceding `<!-- ai-harness:init:start -->`
is empty in the resulting file.

### Requirement: trailing newline preservation

The append path MUST add a single trailing newline to the user's last
line if it lacked one, BEFORE writing the leading blank line + block,
so the user's last line never smashes against the new blank line.

#### Scenario: missing trailing newline handled cleanly
GIVEN an existing `CLAUDE.md` whose last line has no trailing newline
(e.g. literal `"# No trailing newline"` with no `\n`)
WHEN `init_repo` is invoked
THEN the resulting file contains exactly one newline between the
original last line and the leading blank line preceding the new block
AND the original final-line bytes survive (modulo the single appended
`\n`).

### Requirement: empty file is a populated file

An empty agent doc (zero bytes) MUST be treated as the bare-append case:
the system MUST write the init managed block as the file's contents
without an additional leading blank line, so the start marker lands on
the first line.

#### Scenario: empty CLAUDE.md receives the block
GIVEN a `CLAUDE.md` that exists but contains zero bytes
WHEN `init_repo` is invoked
THEN the file ends up containing the new init managed block
AND its first line is the `<!-- ai-harness:init:start -->` marker
(no extra blank line at the very top).

### Requirement: per-file independence

The append path MUST be applied independently per file: a `CLAUDE.md`
that needs appending and an `AGENTS.md` that is missing MUST result in
exactly the actions appropriate to each file (append vs create), with
no cascading behaviour.

#### Scenario: one append, one create
GIVEN a repo root where `CLAUDE.md` exists with content and no markers,
and `AGENTS.md` is absent
WHEN `init_repo` is invoked
THEN `CLAUDE.md` ends up with the block appended to its existing content
AND `AGENTS.md` is created containing only the managed block
AND both files appear in `InitResult.init_block_targets` in deterministic
order (`CLAUDE.md`, then `AGENTS.md`).

## End-to-end coverage

The unit scenarios above cover the in-process `init_repo` seam,
including the empty-file and missing-trailing-newline edge cases.
The user-content invariant is also covered at the binary boundary in
`cover-init-with-e2e.md` — specifically the *append path preserves
existing user content* requirement, which seeds a real disk fixture,
invokes the binary, and asserts on read-back that the recorded
user-authored bytes land at the head of the post-init `CLAUDE.md`
followed by the new init managed block. The leading-blank-line
guarantee in particular is a strong e2e candidate because it is best
verified against a real subprocess write, not a unit-level fixture.
