# Spec — migrate-legacy-agent-doc-block

## Purpose

For an existing agent doc that contains the legacy
`<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` block,
`init_repo` replaces that legacy block **in place** with the new
`<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->` block.
All user content outside the legacy markers survives byte-identical.

This is the migration branch of the four-case decision table — the case
that protects users who wrote their own notes above and/or below the legacy
labels-policy block. A full-file rewrite would discard that content; the
spec demands a surgical substring swap.

## Non-goals

- No preservation of the legacy markers themselves — they are replaced.
- No preservation of any content **inside** the legacy block — that
  content was the old label-policy text and is dropped along with it.
- No handling of legacy markers that appear as substring of larger text
  (e.g. inside a fenced code block). The detection uses a plain substring
  match on the marker lines — see Risks in the PRD.
- No handling of partially-present legacy markers when the *new* markers
  are also present (the new-marker skip branch takes precedence).

## Requirements

### Requirement: surgical substring swap

When an agent doc contains the legacy
`<!-- ai-harness:start -->` / `<!-- ai-harness:end -->` markers
and the new init markers are not already present, the system MUST
replace the legacy block (start-marker line through end-marker line,
inclusive of their newline characters) with the new init managed block,
preserving every byte of content outside the legacy block.

#### Scenario: minimal legacy block swapped
GIVEN a `CLAUDE.md` whose content is exactly the legacy block and nothing
else (the start-marker line, the body, the end-marker line)
WHEN `init_repo` is invoked
THEN the resulting file's bytes equal the new init managed block
AND the new init markers are present
AND the legacy markers are absent.

### Requirement: user content above and below survives

When the legacy block is bounded by user content above and below, the
content outside the legacy block (and the newline that immediately follows
the end marker) MUST be preserved byte-identical.

#### Scenario: prefix and suffix preserved
GIVEN a `CLAUDE.md` whose bytes are exactly
`"prefix line\n<!-- ai-harness:start -->\nold body\n<!-- ai-harness:end -->\nsuffix line\n"`
WHEN `init_repo` is invoked
THEN the resulting file equals
`"prefix line\n" + <new init managed block> + "\nsuffix line\n"`
AND `"prefix line\n"` appears at the head of the file unchanged
AND `"\nsuffix line\n"` appears at the tail of the file unchanged.

### Requirement: per-file migration order

Migration MUST be applied per file in the order `CLAUDE.md`, then
`AGENTS.md`, regardless of which file is missing, legacy, or already
at the new markers. Any file that ends up with the new init markers —
freshly migrated or already-present — appears in
`InitResult.init_block_targets` in that order.

#### Scenario: both files migrated end-to-end
GIVEN a repo root where both `CLAUDE.md` and `AGENTS.md` exist and
each contains only a legacy block (plus optional surrounding user content)
WHEN `init_repo` is invoked
THEN both files end up with the new init managed block
AND any user content outside the legacy block in each file is preserved
AND `InitResult.init_block_targets == ("CLAUDE.md", "AGENTS.md")`.

### Requirement: migration is in place, not a full-file rewrite

The replacement MUST be implemented as a substring swap over the
identified line range, NOT as a "read file → drop everything between
markers → write rest + new block" rewrite. A focused test MUST prove
byte-identical preservation by reading the bytes either side of the
markers before and after the call.

#### Scenario: in-place preservation test
GIVEN a `CLAUDE.md` whose prefix and suffix are recorded verbatim
before init
WHEN `init_repo` is invoked
THEN a substring search for the recorded prefix in the post-init file
returns the start position 0
AND a substring search for the recorded suffix in the post-init file
returns the position equal to `len(prefix) + len(new init managed block) + len(separator newlines)`.

## End-to-end coverage

The byte-preservation invariant is the highest-value e2e target for
the entire change, because the algorithm's safety lives in it and a
real user notices the day any drift slips in. The unit scenario above
proves the algorithm on an in-memory string; the e2e tier proves the
same invariant on real disk after a real subprocess write. See
`cover-init-with-e2e.md` — specifically the *legacy block migration
preserves surrounding bytes* requirement, which seeds a real
`CLAUDE.md` / `AGENTS.md` containing the legacy block bounded by
arbitrary user-authored prefix and suffix, invokes the binary, and
asserts on read-back that the recorded prefix and suffix appear at
the head and tail respectively with the legacy markers absent and
the new init markers present.
