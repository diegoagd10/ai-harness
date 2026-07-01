# Spec — create-coding-standards-skeleton

## Purpose

`init_repo` lands a `CODING_STANDARDS.md` at the repo root containing the
existing titles-only skeleton, but only when the file is absent. The skeleton's
content is unchanged from the pre-refactor version — this spec exists to pin
the *behavior* of the unchanged behavior so a future refactor cannot silently
rewrite the human-edited file.

The capability is independent of the agent-doc work: it is observable in
isolation by running `init_repo` on an empty directory.

## Non-goals

- No edit/expansion of the skeleton bodies — those remain human-authored.
- No re-application over a drifted file — a repurpose is up to the human.
- No change to the `wrote_standards` field on `InitResult`.

## Requirements

### Requirement: skeleton written when file is absent

The system MUST write `CODING_STANDARDS.md` at the repo root with the
existing titles-only skeleton when the file is absent, and MUST set
`InitResult.wrote_standards` to `True` in that case.

#### Scenario: clean directory receives the skeleton
GIVEN an empty repo root (no `CODING_STANDARDS.md`)
WHEN `init_repo` is invoked
THEN `CODING_STANDARDS.md` exists at the repo root
AND its contents equal the existing titles-only skeleton (headings
`# Coding Standards`, `## Style`, `## Testing`, `## Architecture`,
`## Commits`, `## Quality gates` — no body content)
AND `InitResult.wrote_standards` is `True`.

### Requirement: existing file left untouched

The system MUST NOT modify `CODING_STANDARDS.md` when it already exists,
regardless of its current contents, and MUST set
`InitResult.wrote_standards` to `False` in that case.

#### Scenario: pre-existing custom file is preserved byte-identical
GIVEN a repo root where `CODING_STANDARDS.md` already exists with custom
human-authored content
WHEN `init_repo` is invoked
THEN the file's bytes are unchanged
AND `InitResult.wrote_standards` is `False`.

### Requirement: argument default

The system MUST treat a `None` *repo_root* argument as the current working
directory, so the CLI's zero-arg call resolves to the user's repo.

#### Scenario: defaults to cwd when called with no argument
GIVEN a clean directory that the test process has chdir-ed into
WHEN `init_repo()` is called with no argument
THEN `CODING_STANDARDS.md` is created in that directory.

## End-to-end coverage

The unit scenarios above cover the in-process `init_repo` seam. The
same observable contract is also covered at the binary boundary in
`cover-init-with-e2e.md` — specifically the *fresh-init creates the
three repo-local artifacts* requirement, which asserts the on-disk
existence of `CODING_STANDARDS.md` (alongside `CLAUDE.md` /
`AGENTS.md`) after a real `ai-harness init` subprocess invocation,
and the *idempotent re-run on a saturated repo is a no-op*
requirement, which asserts the skeleton's "already exists" CLI echo
plus the file's unchanged mtime on a re-run.
