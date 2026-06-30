# PRD — archive-command

## Intent

Add a first-class archive command contract to the change orchestrator prompt so the existing `nextRecommended: archive` route has explicit, implementation-ready semantics instead of relying on implicit validator wording.

## Scope

### In

- Define archive as an explicit command in `src/ai_harness/resources/change-agent/change-orchestrator.md`.
- State when archive is allowed: validator result is pass or pass-with-warnings with zero critical findings, and no pending tasks remain.
- State when archive is blocked: critical validation findings, missing or failing validation, or pending tasks.
- Make archive behavior explicit as a local change file move with no git, branch, PR, or publishing side effects.
- Keep design documentation aligned with the prompt wording.
- Update prompt rendering assertions if they cover the orchestrator archive contract.

### Out

- Implementing archive execution logic outside the prompt/design contract.
- Adding a separate archive prompt resource unless later design work proves it necessary.
- Changing validator semantics beyond documenting the existing archive gate.
- Publishing GitHub issues or changing issue-tracker workflows.
- Performing any product code edit in this PRD phase.

## Capabilities

- Archive Command Contract: The orchestrator prompt exposes archive as a named command with clear purpose, inputs, allowed states, blocked states, and side-effect boundaries.
- Archive Semantic Gate: The orchestrator tells agents to archive only after validation passes or passes with warnings while reporting zero critical findings.
- Pending Work Guard: The orchestrator blocks archive when any tasks remain incomplete, even if validation has passed.
- Local Move Boundary: The orchestrator defines archive as a local file-system move only, explicitly excluding git, branch, PR, publishing, or remote side effects.
- Prompt/Design Alignment: The design document mirrors the archive command semantics so future prompt changes do not drift from documented behavior.
- Render Assertion Coverage: Existing renderer tests are updated, when needed, to assert the archive command appears with the expected semantics.

## Approach

Lift the archive behavior already implied by the design into the change orchestrator prompt as a narrow command contract. Keep the command focused on orchestration semantics: when archive is recommended, what preconditions must hold, what must block it, and what side effects are forbidden. Align `docs/design/change-orchestrator.md` with the same wording, then adjust prompt rendering tests only where existing assertions need to reflect the new contract.

## Affected Areas

- `src/ai_harness/resources/change-agent/change-orchestrator.md` — primary prompt contract for the archive command.
- `docs/design/change-orchestrator.md` — design documentation aligned with prompt semantics.
- `tests/test_renderers.py` — prompt-body or resource assertions if existing tests inspect the orchestrator output.

## Risks

- Prompt/design drift if archive semantics are changed in one place but not the other.
- Over-specifying execution mechanics that belong to the CLI/state-machine boundary instead of the orchestrator prompt.
- Ambiguous handling of pass-with-warnings if zero-critical requirement is not explicit.
- Accidental implication that archive may publish, commit, branch, or create PRs.

## Rollback Plan

Revert the prompt and design wording changes and restore any affected renderer assertions to their previous expectations. Because this change is documentation/prompt-only, rollback should not require data migration or state repair.

## Dependencies

- Existing validator output semantics, including pass, pass-with-warnings, and critical finding count.
- Existing task completion state used by the orchestrator to decide whether work remains pending.
- Existing local archive behavior or future CLI/state-machine boundary that performs the file move.
- Current renderer tests for prompt content consistency.

## Success Criteria

- `change-orchestrator.md` contains an explicit archive command contract.
- Archive is allowed only for validation pass or pass-with-warnings with zero critical findings and no pending tasks.
- Archive is blocked for missing/failing validation, critical findings, or pending tasks.
- Archive is described as a local file move with no git, branch, PR, publishing, or remote side effects.
- Design documentation stays aligned with the prompt contract.
- Relevant renderer tests pass or are updated to assert the new archive semantics.
