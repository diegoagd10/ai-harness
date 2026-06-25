## Loop variant: tdd skill load

Load the `tdd` skill: `~/.agents/skills/tdd/SKILL.md`. Follow Red → Green → Refactor.

## If blocked

- Comment: `gh issue comment <N> --body "BLOCKED: <one-paragraph reason>"`.
- Return `BLOCKED: <reason>`. Do not close the issue.

## On a fix-up call

- If a gate FAIL the validator reported does not reproduce on your clean tree (gates green,
  `git status --porcelain` empty), do NOT manufacture a no-op commit. Return
  `GATE-NOT-REPRODUCED: <gate>` with the gate output so the orchestrator can arbitrate.

## Hard rules

- Stay on the current branch. No new branches, no switches, no rebases, no force-push, no amends.
- No commented-out code, no `TODO` comments in committed code.
- No drive-by refactors outside the issue's scope.
- `CODING_STANDARDS.md` at the project root owns style, testing, and the gate commands. If it's
  missing, fall back to the project's own lint/test config and proceed cautiously.
