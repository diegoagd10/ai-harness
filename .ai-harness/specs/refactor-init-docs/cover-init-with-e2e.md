# Spec — cover-init-with-e2e

## Purpose

The unit tests in `tests/test_init.py` drive `init_repo` directly and
prove the per-case decision table — but they exercise the in-process
Python seam, not what a user running `ai-harness init` actually sees.
This spec adds the missing tier: an end-to-end test that invokes the
`ai-harness` binary as a real subprocess against a temporary repo root
and observes real disk content, real file mtimes, real stdout/stderr,
and the real exit code.

The e2e tier reuses the existing shell harness at `e2e/e2e_test.sh`
and `e2e/lib.sh`. The init scenarios land under the always-on Tier 1
(no `RUN_FULL_E2E` required) so the new contract is provable on every
CI run.

This spec complements — does not replace — the per-capability specs
in this folder:

| Capability | Per-capability spec | Covered by this e2e spec |
|---|---|---|
| `create-coding-standards-skeleton` | `create-coding-standards-skeleton.md` | Yes — fresh-init creates the three artifacts; skeleton echoes |
| `create-missing-agent-docs` | `create-missing-agent-docs.md` | Yes — fresh-init creates the three artifacts; agent docs carry init markers; byte-identical bodies |
| `append-init-block-to-existing-agent-doc` | `append-init-block-to-existing-agent-doc.md` | Yes — append preserves user content |
| `migrate-legacy-agent-doc-block` | `migrate-legacy-agent-doc-block.md` | Yes — legacy block migration preserves surrounding bytes |
| `skip-when-init-block-present` | `skip-when-init-block-present.md` | Yes — idempotent re-run on saturated repo |
| `emit-cli-echoes` | `emit-cli-echoes.md` | Yes — no label-related output; exit code zero |
| `delete-label-infrastructure` | `delete-label-infrastructure.md` | No — internal cleanup; observable consequence already covered by `emit-cli-echoes` |
| `update-adr-0005` | `update-adr-0005.md` | No — doc-only |

## Non-goals

- No new test framework — the shell-based harness is reused.
- No coverage of `install`, `uninstall`, `set-models`, or other
  commands — those are out of scope for this change.
- No replacement of unit tests. The unit tier in `tests/test_init.py`
  continues to assert the per-case decision table; the e2e tier adds
  binary-boundary coverage that unit tests cannot supply.
- No gating behind `RUN_FULL_E2E` — the init e2e MUST run on every
  default CI run (Tier 1 in the existing harness).
- No coverage of behaviours that are not observable at the binary
  boundary (e.g. module-private helper return shapes, exact field
  names on `InitResult`).

## Requirements

### Requirement: fresh-init creates the three repo-local artifacts

When the system MUST be run against an empty directory, the e2e MUST
observe the three files on disk after the binary returns.

#### Scenario: empty temp repo receives all three files
GIVEN a temp directory with no `CODING_STANDARDS.md`, `CLAUDE.md`, or
`AGENTS.md`
WHEN `ai-harness init` is invoked as a subprocess in that directory
THEN `CODING_STANDARDS.md` exists at the directory root
AND `CLAUDE.md` exists at the directory root
AND `AGENTS.md` exists at the directory root
AND the process exits with code `0`.

### Requirement: created agent docs carry the new init markers

The post-init files on disk MUST contain the new
`<!-- ai-harness:init:start -->` / `<!-- ai-harness:init:end -->`
markers and MUST NOT contain the legacy `ai-harness:start` /
`ai-harness:end` markers.

#### Scenario: both agent docs read back with the new init markers
GIVEN a temp directory with neither agent doc
WHEN `ai-harness init` is invoked
THEN `CLAUDE.md` reads back containing the substring
`<!-- ai-harness:init:start -->`
AND `CLAUDE.md` reads back containing the substring
`<!-- ai-harness:init:end -->`
AND `AGENTS.md` reads back containing both substrings
AND neither file contains the substring `<!-- ai-harness:start -->`.

### Requirement: created agent docs have byte-identical bodies

The on-disk bytes of `CLAUDE.md` and `AGENTS.md` after a fresh init
MUST be equal, and the body MUST reference `CODING_STANDARDS.md` so a
downstream agent knows which file to read.

#### Scenario: created files are byte-for-byte equal on disk
GIVEN a temp directory with neither agent doc
WHEN `ai-harness init` is invoked
THEN `md5sum CLAUDE.md` equals `md5sum AGENTS.md`
AND both files contain the literal string `CODING_STANDARDS.md`.

### Requirement: idempotent re-run on a saturated repo is a no-op

When all three artifacts already exist in their post-refactor state,
re-invoking the binary MUST NOT rewrite any of them (mtimes preserved),
MUST emit per-file "already present — unchanged" wording, and MUST exit
zero.

#### Scenario: second invocation leaves file mtimes unchanged
GIVEN a temp directory where `CLAUDE.md`, `AGENTS.md`, and
`CODING_STANDARDS.md` already exist in their post-refactor state
WHEN the file mtimes (`stat -c %Y`) are recorded
AND `ai-harness init` is invoked
THEN the file mtimes for all three files are unchanged from the
recorded values
AND stdout or stderr contains an "already present" / "unchanged"
indicator for the agent docs
AND `CODING_STANDARDS.md` is reported as already existing or unchanged
AND the process exits with code `0`.

### Requirement: legacy block migration preserves surrounding bytes

When an agent doc carries the legacy `ai-harness:start` /
`ai-harness:end` block bounded by user-authored content above and
below, the binary MUST replace the legacy block in place — keeping
the prefix and suffix byte-identical — and MUST emit the new init
markers.

#### Scenario: user-authored notes above and below the legacy block survive
GIVEN a temp directory where `CLAUDE.md` and `AGENTS.md` each contain
the legacy block bounded by arbitrary user-authored content
(reproducible bytes, including lines that mention "labels" or "loop",
to disambiguate from the migrated body)
WHEN the prefix bytes (everything before the start-marker line) and
suffix bytes (everything after the end-marker line, including the
trailing newline) are recorded
AND `ai-harness init` is invoked
THEN the recorded prefix appears at the head of `CLAUDE.md` unchanged
AND the recorded suffix appears at the tail of `CLAUDE.md` unchanged
AND the same guarantee holds for `AGENTS.md`
AND the legacy markers are absent from both files
AND the new init markers are present in both files
AND the process exits with code `0`.

### Requirement: append path preserves existing user content

When an agent doc exists with user-authored content and no
`ai-harness` markers, the binary MUST append the new init managed
block without disturbing the existing bytes.

#### Scenario: user-authored notes in a populated CLAUDE.md survive
GIVEN a temp directory where `CLAUDE.md` contains user-authored content
and no `ai-harness` markers (the bytes are recorded verbatim)
AND `AGENTS.md` is absent
WHEN `ai-harness init` is invoked
THEN the recorded `CLAUDE.md` content appears in the post-init file
at the head (followed by the new init managed block as the file's
tail)
AND `AGENTS.md` is created containing only the new init managed block
AND the process exits with code `0`.

### Requirement: CLI output contains no label-related strings

The binary MUST NOT emit any reference to the deleted label side
effect — neither on stdout nor on stderr — across the four per-target
outcomes (created / appended-or-migrated / already-present / skipped).

#### Scenario: stdout and stderr are free of label / GitHub / gh / Warning references
GIVEN a temp directory with both agent docs absent
WHEN `ai-harness init` is invoked
THEN stdout does not contain `Created GitHub labels`, `Warning:`,
`ready-for-agent`, `loop` (when meaning the label), or `gh CLI`
AND stderr is empty.

### Requirement: exit code is zero on success and on the no-op path

The binary MUST exit `0` on both a fresh-init run and a saturated-repo
re-run. E2E confirms the contract the per-capability scenarios assert
at the process boundary.

#### Scenario: zero exit on both a fresh and a saturated run
GIVEN two temp directories — one empty and one saturated with the
post-refactor artifacts
WHEN `ai-harness init` is invoked in each
THEN both processes exit with code `0`.
