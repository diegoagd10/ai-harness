# Spec — delete-superseded-adr

## Purpose

Remove `docs/adr/0011-planning-entry-agent-and-size-routing.md` because its
planning rationale is fully captured by the relocated design doc plus ADRs
`0012`, `0013`, and `0014`. The deletion MUST scope-collapse — no other ADR
is touched, and the rationale for the deletion MUST be persisted to the
commit history so auditability survives the file's absence.

## Requirements

### Requirement: ADR 0011 is absent at HEAD

The system MUST delete `docs/adr/0011-planning-entry-agent-and-size-routing.md`
from the working tree at HEAD.

#### Scenario: ADR 0011 path is gone

GIVEN the cleanup commit is applied
WHEN a directory listing of `docs/adr/` is taken at HEAD
THEN no file matching `0011-*` exists.
AND `git cat-file -e HEAD:docs/adr/0011-planning-entry-agent-and-size-routing.md`
exits non-zero.

### Requirement: no other ADR is modified

The system MUST NOT modify, rename, renumber, or delete any other file under
`docs/adr/`. Every surviving ADR MUST be byte-identical to its pre-cleanup
content.

#### Scenario: surviving ADRs are byte-identical

GIVEN a pre-cleanup SHA snapshot of every file under `docs/adr/`
WHEN the cleanup commit is applied
THEN for every surviving file `f` under `docs/adr/` (other than the deleted
0011),
`sha256sum(HEAD:f) == sha256sum(HEAD^:f)`.
AND in particular the two `0008` files,
`docs/adr/0008-worktree-current-branch-and-delete.md` and
`docs/adr/0008-copilot-loop-agents-native-model.md`, are byte-identical.

#### Scenario: ADR 0010 (or the prior ADR) is preserved as the new boundary

GIVEN the cleanup is applied
WHEN the ADR index is read in numeric order at HEAD
THEN the numeric sequence skips from `0010` (or the prior ADR) to `0012`
without any 0011 entry — i.e. no tombstone file, no `0011-SUPERSEDED.md`
file, no placeholder.

### Requirement: successor ADRs encode what 0011 used to encode

The system MUST have successor ADRs `0012`, `0013`, and `0014` present and
load-bearing at HEAD, so deletion of `0011` does not lose architectural
context.

#### Scenario: successor ADRs exist and are unchanged

GIVEN ADR `0011` is deleted
THEN at HEAD,
`docs/adr/0012-file-backed-changes-disk-state-machine.md`,
`docs/adr/0013-change-orchestrator-worktree-branch-pr-agnostic.md`, and
`docs/adr/0014-change-orchestrator-deep-modules.md` all exist.
AND each is byte-identical to its pre-cleanup content.

#### Scenario: successor ADRs are referenced as the supersedes set

GIVEN the cleanup commit is applied
WHEN the commit message body of the deletion commit is read
THEN the body lists the supersedes set — the relocated design doc plus
ADR `0012`, ADR `0013`, and ADR `0014` by their paths or numbers.
AND the body states the prior content is recoverable via
`git show HEAD^:docs/adr/0011-planning-entry-agent-and-size-routing.md` or
an equivalent `git show` invocation.

### Requirement: ADR 0011 content remains recoverable from history

The system MUST keep the prior content of ADR 0011 reachable via git
history, so deletion does not destroy information.

#### Scenario: prior content retrievable from parent commit

GIVEN the cleanup commit `C` is applied
WHEN `git show C^:docs/adr/0011-planning-entry-agent-and-size-routing.md`
is invoked
THEN the command exits zero and returns the full pre-cleanup markdown
content of ADR 0011.
