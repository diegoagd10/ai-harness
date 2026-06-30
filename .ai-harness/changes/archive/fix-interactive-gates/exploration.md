# Exploration — fix-interactive-gates

## Budget
48

## Affected Files
- `src/ai_harness/resources/change-agent/change-orchestrator.md` — source prompt for session-mode, grilling, and phase-routing behavior.
- `tests/test_renderers.py` — current assertions only lock keyword presence; needs stronger behavioral coverage for interactive pause/grill contract.
- `.ai-harness/changes/fix-interactive-gates/prd.md` — later phase must carry explicit gentle-orchestrator references so downstream artifacts inherit the right intent.

## Gentle-Orchestrator Enforcement References
1. `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-149` — SDD Session Preflight hard gate: establishes execution mode before any SDD command; no phase work before choices are collected. Ai-harness enforcement: explicit session-mode decision/default before `change-new`/`change-continue` phase delegation, cached for the session.
2. `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-199` — Execution Mode: interactive pauses after every delegated phase, shows concise result, asks proceed/adjust/stop, STOPs and waits; approval is phase-scoped. Ai-harness enforcement: pause after every Change phase in interactive mode, not only before implementation.
3. `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:200` — proposal/grill round before proposal in interactive mode for business understanding, rules, impact, edge cases, and tradeoffs. Ai-harness enforcement: unclear Change requests enter Grill before `change-new` or before PRD.
4. `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:202-222` — Automatic Mode Gatekeeper: contract/artifact/no-drift/routing checks before auto-continuing. Ai-harness enforcement: auto must be explicit and safety-gated, never accidental fall-through.
5. `/home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:299-308` — Sub-Agent Launch Deduplication: session `(phase, task-fingerprint)` log. Ai-harness enforcement: preserve/strengthen duplicate delegation guard.

## Plan
- Copy the relevant gentle-orchestrator rules into PRD acceptance criteria: hard preflight gate, phase-scoped interactive pauses, and proposal-question round before proposal.
- Tighten change-orchestrator wording so interactive mode means explicit stop-and-ask after every delegated phase, not just before implementation.
- Replace vague renderer assertions with checks for concrete pause/grill language, exact phase scope, and the gentle-orchestrator reference points.
- Re-run prompt-render parity coverage for all native CLIs to ensure the same body change does not drift across render targets.

## Edge Cases
- “interactive” text alone is too weak; the prompt must say STOP / ask / wait at phase boundaries or the behavior can still regress.
- Auto mode must stay explicit and safety-gated; do not blur it with interactive pause semantics.
- Proposal grilling must stay scoped to proposal/start of planning, not every phase and not implementation-only.
- Claude/OpenCode/Copilot render parity can break if tests assume one renderer’s exact wrapping instead of shared body semantics.

## Test Surface
- `uv run pytest tests/test_renderers.py -k change_orchestrator`.
- Assertions for: explicit interactive pause after each delegated phase, proposal-question round before proposal, direct references to gentle-orchestrator preflight/execution-mode rules, and line-reference carry-through into PRD.
- Existing render parity checks for OpenCode/Copilot/Claude must still pass after prompt-body edits.

## Risks
- Overfitting tests to copied prose from gentle-orchestrator instead of the invariant behavior; mitigate by asserting behaviors, not full paragraphs.
- Under-specifying the grill step could leave the orchestrator pausing but not actually clarifying intent.
- Prompt-body edits flow through every native CLI renderer, so a small text change can create broad snapshot drift.
