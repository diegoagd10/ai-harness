# PRD — improve-change-flow

## Intent

Deliver changes as ordered capability slices instead of completing every global phase first. A normal-risk thin slice can be specified, tasked, implemented, validated, and reviewed before later capabilities are elaborated, while unsafe or cross-cutting work retains change-wide design and approval.

## Scope

### In

- Disk-derived identity, order, task association, completion, and routing for the selected capability.
- Slice-scoped prompts, artifacts, feedback checkpoints, and additive status/config-context data.
- Conservative risk classification, approval invalidation, legacy routing, and unchanged archive safeguards.
- Expected rendered resources and focused state, archive, compatibility, and renderer tests.

### Out

- Deterministic validation receipts or attestation formats.
- A generalized task ledger, capability DAG, or cross-slice scheduler.
- Replacing the task CLI, existing within-slice dependency validation, or artifact/archive locations.
- Automatic migration or reinterpretation of legacy artifacts as completed slices.

## Capabilities
- **1. Safe normal-risk first slice (thin initial slice):** Select the first PRD capability, optionally omit design, create only its spec and non-empty task set, implement it, validate it, and present one capability-bound feedback checkpoint; ambiguous or elevated-risk work remains on the safe change-wide path.
- **2. Ordered slice continuation:** After an approved, validated slice, select the next PRD capability and repeat planning through validation without requiring future capability specs or tasks; after the last slice, route to final change validation and archive readiness.
- **3. Risk and scope governance:** Require change-wide design and explicit pre-implementation human approval for high-risk/cross-cutting work, and reopen review when capability order, selected scope, associated tasks, or approved risk changes.

## Approach

Treat PRD capability order as authoritative and derive the minimum selected/completed-slice state from disk. Associate tasks to the selected capability through their existing spec reference and expose only the completion query routing needs. Extend the public status schema additively to identify the current/next capability and slice route.

Normal risk is localized, reversible work with no security/authentication impact, migration, public API/schema compatibility change, cross-module invariant, or broad operational blast radius. Any such concern, explicit high-risk declaration, or classification uncertainty is high risk. Normal-risk automatic flow may reach a working validated slice; interactive review occurs at slice boundaries. High-risk flow requires change-wide design and explicit approval before implementation.

Keep artifacts file-backed and writes atomic. An absent spec, missing or empty task set, unfinished associated task, or missing slice validation cannot complete a slice. Editing approved scope invalidates approval. Slice validation never substitutes for final `validation.md`.

Legacy changes with global artifacts must retain a deterministic safe route or receive explicit migration/review guidance. Missing slice metadata must not imply completion or archiveability. Archive continues to require final validation and every known, non-empty task set complete.

## Affected Areas

- `src/ai_harness/modules/harness/change.py`: slice-aware derivation, additive serialized status, legacy handling, and archive safety.
- `src/ai_harness/modules/harness/tasks.py`: minimal capability/task association and completion query; no new persistence owner or DAG.
- `src/ai_harness/resources/change-agent/change-{orchestrator,propose,design,specs,tasks,implementor,validator}.md`: slice execution, checkpoints, and escalation rules.
- `expected/change-*.md`: renderer fixtures for all changed resources and supported render targets.
- `tests/test_change.py`, `tests/test_renderers.py`: routing, risk, compatibility, archive, and rendered-contract coverage.

## Risks

- Artifact presence may falsely signal slice completion; require identity, association, non-empty tasks, task completion, and validation.
- Additive route/status fields may break consumers; version and test serialization while preserving existing fields.
- Relaxed checkpoints may bypass safety; classify conservatively and keep explicit high-risk approval.
- PRD edits may stale derived state; detect affected identity/order/scope and reopen review.

## Rollback Plan

Revert slice-aware routing and prompt changes together, restoring global phase recommendation. Preserve existing artifacts/tasks; additive state must be ignorable. Do not weaken archive preflight during rollout or rollback.

## Dependencies

Target Python 3.12+. Use existing Typer/questionary CLI seams and `uv`, `ruff`, and `pytest`; avoid new runtime dependencies. Follow current module ownership, atomic file-write patterns, TDD, and per-task commits formatted `[improve-change-flow][task_id] slug`.

## Success Criteria

- A normal-risk multi-capability change delivers and validates capability 1 before capability 2 needs a spec or tasks.
- One-capability work routes from slice validation to final validation/archive, never to a nonexistent slice.
- High-risk or cross-cutting work cannot implement without change-wide design and explicit approval; relevant edits reopen approval.
- Malformed, missing, empty, and legacy slice inputs produce safe actionable routing, never false completion.
- Final archive still requires all known tasks complete and final `validation.md`.
- Updated `pytest` coverage and renderer fixtures pass across OpenCode, Claude, and Copilot; `ruff` gates pass.
