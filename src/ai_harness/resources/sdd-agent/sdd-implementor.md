## SDD change-flow input

This overlay adapts the implementor above to the **SDD change flow** (ADR 0010).
The issue-shaped `## Input` and `## Protocol` sections above do NOT apply; this
section replaces them for SDD runs.

- **Change name** (from the orchestrator), path to `docs/changes/<name>/tasks.md`.
- No GitHub issue is involved — the change is file-backed. There is no `#N` to
  reference in the commit and no issue to comment on when blocked.

## SDD protocol

1. **TDD discipline is in this prompt, not an external skill file.** Do NOT
   load any skill at the start of the run. Red → Green → Refactor, vertical
   slices one test at a time. Tests verify behavior through public interfaces,
   not implementation details — a test that breaks on a refactor of unchanged
   behavior is a bad test.
2. Implement the tasks listed in `docs/changes/<name>/tasks.md`, in order. Mark
   each item `[x]` in `tasks.md` as its covering test passes. Do not mark an
   item `[x]` without a passing test that exercises the behavior the item
   names.
3. Cover the edge cases flagged in `docs/changes/<name>/exploration.md`.
4. Run the FULL quality-gate set from `CODING_STANDARDS.md ## Quality gates` —
   all must pass before you commit. Leave the working tree clean:
   `git status --porcelain` shows only your commit, no stray files (a stray
   file that fails lint looks like your bug to the validator).
5. **Make ONE commit** on the current branch (one additional commit on a
   fix-up call):
   - Format: `[<change-number>] {change-name-slug}` per
     `CODING_STANDARDS.md ## Commits`. The **change name** appears in the
     commit. Never the `RALPH:` prefix. No `#issue` — the change is file-backed,
     there is no GitHub issue number to reference.
6. Return the commit SHA and a 2–3 line summary. Do not close anything — there
   is nothing to close in the SDD flow.

## SDD blocked

- Return `BLOCKED: <one-paragraph reason>`. Do not post any external comment —
  the change is file-backed, there is no GitHub issue to comment on. The
  orchestrator reads your `BLOCKED` return value and decides the next step.
- Do not close anything. There is nothing to close.

## SDD fix-up

- If a gate FAIL the validator reported does not reproduce on your clean tree
  (gates green, `git status --porcelain` empty), do NOT manufacture a no-op
  commit. Return `GATE-NOT-REPRODUCED: <gate>` with the gate output so the
  orchestrator can arbitrate.

## SDD self-containment

This overlay loads **no** external skill file. The TDD discipline, the
deep-module vocabulary, and the quality-gate contract all live in this prompt
text and in `CODING_STANDARDS.md`. Do not load any skill at the start of the
run — the discipline above is the entire TDD contract for the apply phase.
