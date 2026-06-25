## SDD change-flow input

This overlay adapts the explorer above to the **SDD change flow** (ADR 0010).
The issue-shaped `## Input` section above does NOT apply; this section replaces
it for SDD runs.

- **Change name** (from the orchestrator), path to `docs/changes/<name>/`.
- No GitHub issue is involved — the change is file-backed. There is no `#N` to
  reference and no issue body to read.

## SDD protocol

1. Read `docs/changes/<name>/` to see which artifacts already exist
   (`proposal.md`, `spec.md`, `design.md`, `tasks.md`, `exploration.md`,
   `verify-report.md`). Derive which phase is next from the artifact set — no
   manual status label, no GitHub label.
2. If `proposal.md` exists, read it first — it is the change's intent. If
   `spec.md` or `design.md` exist, read them next — they constrain the
   implementation surface this exploration informs.
3. Scan the affected code (read-only): skim the surrounding code, not just the
   file you'd change. Prefer concrete file paths over abstractions.
4. Ambiguous change → list it under `Risks / unknowns`; do not invent a plan.
5. Preexisting behavior that looks like a bug → flag it under
   `Risks / unknowns` as `preexisting, possibly wrong: preserve or fix?` so the
   implementor and validator share one expectation, instead of fighting over it
   in the fix-up loop.

## SDD output

Write `docs/changes/<name>/exploration.md` (≤ 60 lines, same section schema as
the `## Output` section above: Affected files / Plan / Edge cases / Test
surface / Risks / unknowns). The orchestrator passes this file's path to the
implementor; the implementor does not re-discover the plan.

## SDD self-containment

This overlay loads **no** external skill file. The TDD discipline, the
deep-module vocabulary, and the quality-gate contract all live in this prompt
text and in `CODING_STANDARDS.md`. Do not load any skill at the start of the
run — the discipline above is the entire TDD contract for the explore phase.
