# Design — whole-repo-cleanup-review

## Context

The repo carries durable design narrative at `docs/design/change-orchestrator.md`
that documents a Change (`borrow-gentle-orchestrator`) already archived under
`.ai-harness/changes/archive/borrow-gentle-orchestrator/`. Active doc readers
hit two problems:

1. The durable design lives outside the change archive it describes — when a
   future explorer loads the change, they have to cross-reference a separate
   `docs/` tree to find the design source.
2. ADR `0011-planning-entry-agent-and-size-routing.md` is superseded by the
   change-orchestrator design (and by ADRs `0012`/`0013`/`0014`) but still
   ships as an active ADR, inflating the active doc surface.

This Change relocates the design doc into its owning archive folder and
deletes the superseded ADR. The "deep module" here is the cleanup operation
itself: its **interface** is the post-change repository state plus the audit
trail; its **implementation** hides the `git` mechanics, the grep sweep, and
the cross-reference rewrites.

## Deep modules

### `archive-design-doc` — relocate the durable design into its change folder

- **Seam**: filesystem state at the two paths
  `docs/design/change-orchestrator.md` (old) and
  `.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
  (new).
- **Interface**:
  - `docs/design/change-orchestrator.md` MUST NOT exist post-change.
  - `.ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`
    MUST exist post-change.
  - The new file MUST be **byte-identical** to the pre-change source (no
    content edits during the move — same SHA).
  - `git log --follow` on the new path MUST return the full prior history of
    the old path (history-following is the whole point of using `git mv`).
- **Hides**: the `git mv` mechanics, the `mkdir -p` of the target directory if
  absent (target already exists — see Move mechanics below), and the
  archive-internal evidence-link rewrites listed in `no-stale-references`.
- **Depth note**: caller sees "old path gone, new path present, history
  followed" — the seam hides all eleven archive-internal files that cite the
  old path (`archive/borrow-gentle-orchestrator/{design,exploration,prd,implementation,validation}.md`,
  `archive/borrow-gentle-orchestrator/specs/*.md` (3 files), and
  `archive/borrow-gentle-orchestrator/tasks.json`).

### `delete-superseded-adr` — remove ADR 0011

- **Seam**: filesystem state at `docs/adr/`.
- **Interface**:
  - `docs/adr/0011-planning-entry-agent-and-size-routing.md` MUST NOT exist
    post-change.
  - All other ADRs in `docs/adr/` MUST be **byte-identical** to their pre-change
    content (especially the two `0008` files — they share a number, but both
    are live and stay live).
  - `git log` on the repo MUST still return the prior content of ADR 0011
    reachable via the deletion commit (auditability).
- **Hides**: the `git rm` mechanics, the `supersedes` rationale (encoded in
  the commit message body — see Delete mechanics), and the prior-content
  recovery path (`git show <commit>^:docs/adr/0011-...`).
- **Depth note**: caller sees "ADR 0011 absent, others untouched" — the seam
  hides the justification (later ADRs `0012`/`0013`/`0014` plus the relocated
  design doc together encode everything 0011 was load-bearing for).

### `preserve-protected-paths` — invariant guard for skills and runtime prompt

- **Seam**: byte-equality check on three protected path sets.
- **Interface**:
  - `.agents/skills/**` MUST be unchanged (presence + byte-equality of every
    file under the tree).
  - `.claude/skills/**` MUST be unchanged (same).
  - `src/ai_harness/resources/change-agent/change-orchestrator.md` MUST be
    **byte-identical** to the pre-change file (this is the load-bearing
    runtime prompt shipped via the package resources system — discovered from
    `src/ai_harness/resources/{loop-agent,change-agent}` and rendered into CLI
    agent files).
- **Hides**: the pre-change snapshot hash, the diff machinery, and the
  `change-validator` invocation that performs the comparison.
- **Depth note**: a single seam hides the "is anything in the protected set
  dirty?" question. The three sets are addressed together because they are
  the same class of failure: silent breakage of runtime contracts.

### `no-stale-references` — sweep cross-references after both moves

- **Seam**: grep results for three patterns across the active repo (excluding
  `.git/`, archived changes, and the moved file at its new location).
- **Interface**: zero hits for each of:
  - `docs/design/change-orchestrator.md`
  - `0011-planning-entry-agent-and-size-routing`
  - `ADR 0011`
  Acceptance permits hits inside the `borrow-gentle-orchestrator/` archive's
  historical notes that pre-date this Change (they are evidence, not active
  links) and inside the PR/issue metadata that pre-dates this Change.
- **Hides**: the per-file patches (archive-internal evidence citations
  pointing to old line ranges; line citations that renumber if the moved
  file's bytes happen to shift — they should not, since the move is
  byte-identical).
- **Depth note**: caller asks one question — "are there broken links?" — and
  gets a yes/no. The seam hides which files were touched and how line ranges
  were renumbered (they aren't, in practice, because the move preserves
  bytes).

## Internal collaborators

These are **not** public test seams — they exist so the four public seams above
can be tested transitively. They are never mocked.

- **`git-mv-runner`** — wraps `git mv <src> <dst>`; verifies post-run that the
  new path exists, the old path does not, and `git log --follow <dst>` returns
  at least one commit prior to this Change. Used by `archive-design-doc`.
- **`git-rm-runner`** — wraps `git rm <path>`; verifies post-run that the path
  is absent and `git show HEAD^:<path>` still returns the prior content. Used
  by `delete-superseded-adr`.
- **`protected-snapshot`** — hashes every file under the three protected paths
  before the change, exposes a `verify_unchanged()` method for after. Used by
  `preserve-protected-paths`.
- **`reference-sweeper`** — runs the three grep patterns, returns structured
  hit lists grouped by file and category (active-doc hit vs archive-internal
  historical note vs pre-Change PR/issue metadata). Used by
  `no-stale-references`.
- **`evidence-link-rewriter`** — given the set of "active-doc" hits from
  `reference-sweeper`, rewrites path strings and renumbers line-range
  citations where necessary. Only fires if `git mv` somehow shifted bytes
  (it should not).
- **`change-validator-runner`** — invokes `change-validator` after the
  operation; collects its verdict per acceptance criterion. Used by all four
  public seams (the validator is the final witness).

## Seam map

```
              archive-design-doc  ─┐
              delete-superseded-adr ─┤
              preserve-protected-paths ─┼──►  change-validator-runner
              no-stale-references ─────┘             │
                                                     ▼
                                              post-change repo state
                                              (audit trail = commit msg)
```

Four public seams → one validator witness. Internal collaborators feed the
seams, never the validator directly. The fewer cross-module seams, the
better: every operation routes through `change-validator` so a single
verdict covers all four capabilities.

## Rejected alternatives

- **`mv` instead of `git mv`** — rejected. Plain `mv` would leave the file
  untracked at the new path and orphan the prior history. The design depends
  on `git log --follow` returning the prior lineage of the file, which only
  `git mv` preserves. The seams assume history-following; cheaper mechanics
  would break the audit-trail invariant.
- **Keep ADR 0011 and just add a "superseded" note** — rejected. ADR 0011
  has zero remaining load-bearing references outside itself; the relocated
  design doc plus ADRs `0012`/`0013`/`0014` together cover everything 0011
  once encoded. The "superseded note" alternative would inflate the active
  ADR surface without paying back any reference cost — a shallow module.
  Deletion is the deeper choice.
- **Rename ADR 0011 to `0011-SUPERSEDED.md` instead of deleting** —
  rejected for the same reason. A renamed tombstone still occupies the ADR
  numbering sequence and shows up in ADR indexes / greps. The deletion test
  fails: it concentrates complexity (a stale file the explorer has to read
  and dismiss) rather than removing it.
- **Bundle the ADR 0008 numbering collision into this Change** — rejected.
  Both `0008-worktree-current-branch-and-delete.md` and
  `0008-copilot-loop-agents-native-model.md` have live references; the
  collision resolution needs its own evidence-backed follow-up. Bundling it
  here would widen the blast radius past the "no product code, no skill
  edits, no ADR renumbering" invariants.
- **Move the design doc to `docs/design/_archive/` instead of into the
  change folder** — rejected. The whole point of the move is that durable
  design lives with the change it documents. A `docs/design/_archive/`
  target keeps the design in the active `docs/` tree (just under a different
  folder) — the explorer still has to cross-reference it. The change-folder
  target is the only path that satisfies the PRD's "durable design travels
  with the change history it belongs to" capability.
- **Edit `docs/design/change-orchestrator.md` before moving (drop the 5
  in-file references to ADR 0011)** — **DEFERRED, not chosen**. The file
  cites ADR 0011 on lines 4, 6, 559, 644, 649. After ADR 0011 is deleted,
  those references become stale-by-absence. The PRD scopes "no content
  edits during the move" (`archive-design-doc` capability: "preserving the
  file's bytes verbatim"). We honour that — the move is byte-identical — and
  surface this as a **follow-up note** in the Change's validation step: the
  relocated file at its new path retains those 5 in-file references as
  historical evidence of 0011's influence on the design lineage. A separate,
  evidence-backed Change can rewrite those references (e.g. to "ADR lineage
  0012/0013/0014") if a future cleanup wants them tightened. Doing it in this
  Change would violate the "byte-identical move" invariant.

## Move mechanics

1. Verify target directory exists:
   `.ai-harness/changes/archive/borrow-gentle-orchestrator/` already contains
   `design.md`, `exploration.md`, `implementation.md`, `prd.md`, `tasks.json`,
   `validation.md`, and `specs/`. **No `mkdir` needed.** The target filename
   `change-orchestrator.md` does **not** collide with the sibling `design.md`
   in that folder (different names).
2. Snapshot hashes of the three protected path sets via `protected-snapshot`.
3. `git mv docs/design/change-orchestrator.md
   .ai-harness/changes/archive/borrow-gentle-orchestrator/change-orchestrator.md`.
4. `git rm docs/adr/0011-planning-entry-agent-and-size-routing.md`.
5. Run `reference-sweeper`; for any active-doc hit, patch via
   `evidence-link-rewriter` (archive-internal hits are left alone per the
   PRD's "historical notes" allowance).
6. `change-validator-runner` confirms every acceptance criterion.
7. **Human review gate** (non-optional) before archive.

## Delete mechanics

`git rm docs/adr/0011-planning-entry-agent-and-size-routing.md` removes the
file from the working tree and stages the deletion. The commit message body
MUST capture the `supersedes` rationale:

```
docs(cleanup): delete superseded ADR 0011

ADR 0011 (planning entry-agent and size-based routing) is fully
superseded by:
- docs/design/change-orchestrator.md (relocated in this commit)
- ADR 0012 (file-backed changes disk state machine)
- ADR 0013 (change orchestrator worktree branch PR-agnostic)
- ADR 0014 (change orchestrator deep modules)

Prior content is recoverable via `git show HEAD^:docs/adr/0011-planning-entry-agent-and-size-routing.md`.
```

The body text is the durable `supersedes` edge — it survives in commit
history even after the file is gone.