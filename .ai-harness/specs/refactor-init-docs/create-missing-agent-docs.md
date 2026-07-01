# Spec — create-missing-agent-docs

## Purpose

For each of `CLAUDE.md` and `AGENTS.md` that does not exist, `init_repo`
creates it containing only the new init managed block. The two files are
created independently and identically — the same managed body lives in both.

This is the load-bearing behaviour that replaces the pre-refactor
"skip when no agent doc" path: post-refactor, a clean repo receives **both**
agent docs, so a downstream agent (Claude Code, OpenCode, generic) always
finds its persona file with the init block already in place.

## Non-goals

- No write when the file already exists (covered by
  `skip-when-init-block-present` and `append-init-block-to-existing-agent-doc`).
- No content differentiation between the two files — they MUST match byte-for-byte.
- No header/intro prepended above the managed block on the create path
  (the block is the file's entire contents).

## Requirements

### Requirement: both agent docs created when missing

The system MUST create `CLAUDE.md` at the repo root when absent and MUST
create `AGENTS.md` at the repo root when absent. The created file's contents
MUST be the new init managed block (markers + one-line body pointing to
`CODING_STANDARDS.md`) and nothing else.

#### Scenario: clean directory receives both files
GIVEN a repo root with neither `CLAUDE.md` nor `AGENTS.md`
WHEN `init_repo` is invoked
THEN both files exist at the repo root
AND each file's contents equal the new init managed block exactly
AND `CLAUDE.md` is created before `AGENTS.md` (deterministic order).

### Requirement: only the missing file is created

The system MUST create a single missing agent doc without disturbing any
agent doc that already exists.

#### Scenario: one missing, one present
GIVEN a repo root where `AGENTS.md` already exists with custom content
and `CLAUDE.md` is absent
WHEN `init_repo` is invoked
THEN `CLAUDE.md` is created at the repo root with the new init managed block
AND `AGENTS.md` is unchanged (no rewrite, no append — its existing bytes
are preserved).

### Requirement: identical managed body across both files

The created `CLAUDE.md` and `AGENTS.md` MUST contain byte-identical
contents — same encoding, same line endings, no trailing-newline drift.

#### Scenario: created files have matching bytes
GIVEN a repo root with neither agent doc
WHEN `init_repo` is invoked
THEN reading both files back yields equal byte strings (`==` on the
`Path.read_bytes()` results).

### Requirement: managed body references CODING_STANDARDS.md

The new init managed block's body MUST explicitly reference
`CODING_STANDARDS.md` so a downstream agent knows which file to read.

#### Scenario: body points at CODING_STANDARDS.md
GIVEN a repo root with neither agent doc
WHEN `init_repo` is invoked
THEN the literal substring `CODING_STANDARDS.md` appears in both
created files.

## End-to-end coverage

The unit scenarios above cover the in-process `init_repo` seam. The
same observable contract is also covered at the binary boundary in
`cover-init-with-e2e.md` — specifically the *fresh-init creates the
three repo-local artifacts*, *created agent docs carry the new init
markers*, and *created agent docs have byte-identical bodies*
requirements, which together assert (from a real subprocess
invocation) the on-disk creation of `CLAUDE.md` and `AGENTS.md`, the
presence of the new `<!-- ai-harness:init:start -->` /
`<!-- ai-harness:init:end -->` markers, the absence of the legacy
markers, and `md5sum` equality of the two files.
