# PRD — fix-interactive-gates

## Intent

Fix `change-orchestrator` so interactive mode is an enforceable control flow, not wording. The observed failure is that `change-orchestrator` auto-ran `explore -> prd -> design -> specs -> tasks` in interactive mode, without stopping for phase-scoped approval. It also failed to grill or clarify an ambiguous request even though prior memory showed archive intent could mean manual archive rather than CLI implementation. Current tests and prompt assertions mostly check for wording, so behavior can regress while keywords remain present.

This Change must make ai-harness match the relevant gentle-orchestrator enforcement model and carry those references forward for design, specs, tasks, implementation, and validation.

## Scope

### In

- Strengthen `change-orchestrator` prompt behavior for interactive and automatic execution modes.
- Add an explicit session-mode hard gate/default before `change-new` or `change-continue` phase delegation, with the decision cached for the session.
- Require interactive stop/ask/wait behavior after every delegated Change phase, with approval scoped only to the next phase.
- Require a grill/proposal question gate before PRD when request understanding is weak or intent is ambiguous.
- Make automatic mode explicit and safety-gated so auto-run cannot occur by accidental fall-through.
- Preserve or strengthen duplicate sub-agent launch prevention.
- Harden renderer tests so they verify concrete behavior, not keyword presence.

### Out

- No CLI archive command implementation in this Change.
- No changes to the `gentle-ai` repo.
- No product-code implementation during the PRD phase.
- No issue publishing from this Change phase.

## Capabilities

- Session mode hard gate/default and session cache: Before any `change-new` or `change-continue` phase delegation, the orchestrator must establish execution mode, apply an explicit default when needed, and cache the session decision so later routing cannot silently change behavior.
- Interactive between-phase stop/wait gate after every delegated phase: In interactive mode, the orchestrator must pause after every delegated Change phase, show a concise phase result, ask whether to proceed, adjust, or stop, then STOP and wait. Approval is phase-scoped and cannot be interpreted as permission to run the whole pipeline.
- Grill/proposal question gate for unclear intent: When request intent or business understanding is weak, the orchestrator must enter a Grill/proposal-question round before `change-new` or before PRD, covering business understanding, rules, impact, edge cases, and tradeoffs.
- Explicit auto-mode gatekeeper: Automatic mode must be explicit and must pass contract, artifact, no-drift, and routing checks before continuing. Auto mode must never be accidental default fall-through from interactive or unspecified mode.
- Duplicate delegation guard: The orchestrator must preserve or strengthen a session `(phase, task-fingerprint)` log so the same phase/task cannot be launched repeatedly in one session.
- Render/test contract hardening: Tests must assert enforceable interactive behavior: stop/ask/wait after each phase, phase-scoped approval, grill/proposal question preservation, explicit auto-mode gatekeeping, and gentle-orchestrator reference carry-through.

## Approach

Use gentle-orchestrator as the normative source for enforcement semantics, while implementing parity in ai-harness Change terminology:

- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-149` — SDD Session Preflight hard gate: execution mode established before SDD work; no phase work until choices collected. Required ai-harness parity: explicit session-mode decision/default before `change-new`/`change-continue` phase delegation, cached for session.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-199` — Execution Mode: interactive pauses after every delegated phase, shows concise result, asks proceed/adjust/stop, STOPs and waits; approval is phase-scoped. Required ai-harness parity: pause after every Change phase in interactive mode, not only before implementation.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:200` — proposal/grill round before proposal in interactive mode covering business understanding, rules, impact, edge cases, tradeoffs. Required ai-harness parity: unclear Change requests enter Grill before `change-new` or before PRD.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:202-222` — Automatic Mode Gatekeeper: contract/artifact/no-drift/routing checks before auto-continuing. Required ai-harness parity: auto must be explicit and safety-gated, never accidental fall-through.
- `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:299-308` — Sub-Agent Launch Deduplication: session `(phase, task-fingerprint)` log. Required ai-harness parity: preserve/strengthen duplicate delegation guard.

Downstream work should update the shared `change-orchestrator` source prompt first, then harden renderer coverage around behavior invariants rather than full prose snapshots. The final prompt must make approval of one phase insufficient to continue through later phases without another stop/ask/wait boundary.

## Affected Areas

- `src/ai_harness/resources/change-agent/change-orchestrator.md` — source prompt for session-mode selection, interactive phase gates, grill/proposal question routing, auto-mode gatekeeper checks, and duplicate launch protection.
- `tests/test_renderers.py` — behavioral renderer assertions for `change-orchestrator` across native CLI render targets.
- `.ai-harness/changes/fix-interactive-gates/` — SDD artifacts for this Change.

## Risks

- Tests may overfit to copied prose instead of enforcing control-flow behavior.
- Prompt wording could still permit pipeline-wide approval if phase-scoped approval is not explicit enough.
- Grill/proposal gate may become too vague and fail to trigger for ambiguous intent like archive/manual archive ambiguity.
- Auto mode may be described as a convenience path and accidentally become fallback behavior unless gatekeeper checks are mandatory.
- Renderer parity may break if tests assume one renderer's wrapping instead of shared prompt-body semantics.

## Rollback Plan

Revert changes to `src/ai_harness/resources/change-agent/change-orchestrator.md` and related renderer tests. Since this Change only affects orchestrator prompt behavior and tests, rollback should restore the previous prompt contract without data migration or external service changes.

## Dependencies

- Prior exploration artifact at `.ai-harness/changes/fix-interactive-gates/exploration.md`.
- Gentle-orchestrator reference behavior from `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md` line ranges listed above.
- Existing renderer parity test harness in `tests/test_renderers.py`.

## Success Criteria

- PRD preserves exact gentle source refs and ai-harness parity mapping.
- Final prompt makes interactive approval phase-scoped and cannot be read as pipeline-wide approval.
- Tests fail if interactive wording only says “pause” without stop/ask/wait after each phase.
- Tests fail if grill/proposal question round disappears.
- Tests fail if auto mode can be described as default fall-through without gatekeeper checks.
- `change-orchestrator` no longer auto-runs `explore -> prd -> design -> specs -> tasks` in interactive mode without explicit phase-by-phase approval.
- Ambiguous Change requests with weak understanding enter Grill before `change-new` or before PRD.
