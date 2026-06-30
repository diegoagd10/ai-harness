# Exploration — cli-owned-archive

## Budget
340

## Affected Files
- src/ai_harness/modules/harness/change.py — add archive operation, preflight checks, and file-move logic.
- src/ai_harness/commands/change.py — add `change-archive` CLI adapter and JSON error shaping.
- src/ai_harness/main.py — register new top-level command.
- src/ai_harness/resources/change-agent/change-orchestrator.md — switch archive routing to `change-archiver` and terminal semantics.
- src/ai_harness/resources/change-agent/change-archiver.md — new subagent prompt resource.
- src/ai_harness/modules/harness/renderers.py — expand change-agent metadata / spawn allowlist.
- src/ai_harness/modules/wizard/pure.py — add archive agent to OpenCode change-agent vocabulary.
- tests/test_change.py — archive command and move semantics coverage.
- tests/test_renderers.py — prompt discovery, allowlist, and agent-count expectations.
- tests/test_install.py — rendered agent discovery/count expectations.
- tests/test_set_models.py — OpenCode change-agent vocabulary and re-render scope.

## Plan
- Add `change_archive(root, change)` seam that validates all structural preconditions before any move.
- Move specs to `.ai-harness/specs/{change}/...`, then move remaining change folder to `.ai-harness/archive/{change}`.
- Keep archive CLI output to plain `done`; surface failures as `{ "errors": [...] }` with non-zero exit.
- Add `change-archiver` prompt and wire orchestrator/rendering/wizard registries to the new agent.
- Update tests for the new agent count, allowlist, archive path, and terminal routing.

## Edge Cases
- Missing change folder, missing `validation.md`, incomplete tasks, existing specs target, or existing archive target must fail before mutation.
- Transactionality matters: if a move fails after preflight, implementation needs rollback or staging so partial archive does not leak.
- Archived folder must retain planning/report files but exclude `specs/` entirely.
- Current docs/code still describe archive under `changes/archive/{name}`; implementation must avoid inheriting that stale layout.

## Test Surface
- `tests/test_change.py` CLI success/failure + path moves.
- `tests/test_renderers.py` change-agent discovery, prompt set, and spawn allowlist.
- `tests/test_install.py` OpenCode render discovery count.
- `tests/test_set_models.py` change-agent vocabulary and override scope.

## Risks
- File moves are harder to make atomic than phase-artifact writes; use staging or rollback to preserve all-or-nothing semantics.
- Several hard-coded 8/12 counts will drift unless every change-agent registry and test fixture gets updated together.
- Old archive-path assumptions in docs/tests can silently diverge from the new top-level archive layout.
