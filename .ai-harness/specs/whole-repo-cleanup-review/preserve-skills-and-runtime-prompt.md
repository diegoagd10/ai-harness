# Spec — preserve-skills-and-runtime-prompt

## Purpose

Negative-assertion guard. Keep the runtime contract intact: skill trees
(`.agents/skills/**` and `.claude/skills/**`) and the load-bearing runtime
prompt under `src/ai_harness/resources/change-agent/` MUST be untouched by
this Change. Any drift in these paths would break runtime behavior; this
spec asserts that does not happen.

## Requirements

### Requirement: `.agents/skills/**` is unchanged

The system MUST NOT modify, add, or delete any file under
`.agents/skills/**`.

#### Scenario: every skill file in `.agents/skills/` is byte-identical

GIVEN a pre-cleanup enumeration of all files under `.agents/skills/`
recorded with their SHA-256 hashes
WHEN the cleanup commit is applied
THEN for every file `f` previously enumerated under `.agents/skills/`,
`sha256sum(HEAD:f) == sha256sum(HEAD^:f)`.
AND the set of file paths under `.agents/skills/` at HEAD equals the set at
`HEAD^` (no addition, no removal).

#### Scenario: no `.agents/skills/` file appears in the cleanup diff

GIVEN the cleanup commit is applied
WHEN the diff for the commit is inspected
THEN no path matching `^\.agents/skills/` appears in the diff (zero files
added, zero files removed, zero files modified).

### Requirement: `.claude/skills/**` is unchanged

The system MUST NOT modify, add, or delete any file under
`.claude/skills/**`.

#### Scenario: every skill file in `.claude/skills/` is byte-identical

GIVEN a pre-cleanup enumeration of all files under `.claude/skills/`
WHEN the cleanup commit is applied
THEN for every file `f` previously enumerated under `.claude/skills/`,
`sha256sum(HEAD:f) == sha256sum(HEAD^:f)`.
AND the set of file paths under `.claude/skills/` at HEAD equals the set at
`HEAD^`.

#### Scenario: no `.claude/skills/` file appears in the cleanup diff

GIVEN the cleanup commit is applied
WHEN the diff for the commit is inspected
THEN no path matching `^\.claude/skills/` appears in the diff.

### Requirement: runtime prompt
`src/ai_harness/resources/change-agent/change-orchestrator.md` is unchanged

The system MUST keep
`src/ai_harness/resources/change-agent/change-orchestrator.md`
byte-identical to its pre-cleanup content. This file is shipped via the
package resources system and rendered into CLI agent files at runtime;
any drift would silently change agent behavior.

#### Scenario: runtime prompt SHA is invariant

GIVEN `SRC_SHA = sha256sum(HEAD^:src/ai_harness/resources/change-agent/change-orchestrator.md)`
recorded before cleanup
WHEN the cleanup commit is applied
THEN
`sha256sum(HEAD:src/ai_harness/resources/change-agent/change-orchestrator.md) == SRC_SHA`.

#### Scenario: runtime prompt is not in the cleanup diff

GIVEN the cleanup commit is applied
WHEN the diff for the commit is inspected
THEN no path matching
`^src/ai_harness/resources/change-agent/change-orchestrator\.md$` appears in
the diff.

### Requirement: the three protected sets are evaluated together

The system MUST evaluate the three protected path sets in a single
post-cleanup pass and report on all three atomically. Failure on any one
fails the whole guard.

#### Scenario: combined guard verdict is green at HEAD

GIVEN the cleanup commit is applied
WHEN the post-cleanup guard runs against HEAD
THEN it reports `PASS` for all three protected sets:
`.agents/skills/**`, `.claude/skills/**`, and
`src/ai_harness/resources/change-agent/change-orchestrator.md`.
AND no individual set reports `FAIL`.

#### Scenario: a hypothetical drift in any set fails the guard

GIVEN the cleanup were to introduce even a single-byte change to any file
under one of the three protected sets
WHEN the post-cleanup guard runs
THEN it reports `FAIL` for that set
AND the overall guard verdict is `FAIL` (no per-set short-circuit that lets
sibling sets pass).
