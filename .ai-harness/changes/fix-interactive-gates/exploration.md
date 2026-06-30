# Exploration — fix-interactive-gates

## Budget
16

## Affected Files
- .ai-harness/changes/fix-interactive-gates/exploration.md — revision target for scope and contract notes
- /home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:100-149 — SDD Session Preflight hard gate; ai-harness must require explicit session-mode choice, default it deliberately, and cache it
- /home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:178-199 — Execution Mode; ai-harness interactive flow must pause after every delegated phase, show concise result, ask proceed/adjust/stop, and keep approval phase-scoped
- /home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:200 — proposal question/grill round; ai-harness must route unclear change requests into Grill before `change-new` or before PRD/proposal work
- /home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:202-222 — Automatic Mode Gatekeeper; ai-harness auto mode needs distinct safety language and explicit contract/artifact/no-drift checks
- /home/diegoagd10/Projects/gentle-ai/internal/assets/opencode/sdd-orchestrator.md:299-308 — Sub-Agent Launch Deduplication; ai-harness must prevent duplicate launches with session-scoped `(phase, task-fingerprint)` logging

## Plan
- Revise exploration to name each gentle-orchestrator enforcement explicitly, with line references.
- Tie 100-149 to ai-harness-side session-mode decision/default caching.
- Tie 178-199 to ai-harness interactive pauses after each delegated phase, not just before implementation.
- Tie 200 to Grill routing before `change-new` or PRD/proposal when change request is unclear.
- Tie 202-222 to a distinct auto-mode gatekeeper safety contract, separate from interactive wording.
- Tie 299-308 to tests and orchestration guards for duplicate-launch prevention via session-scoped fingerprints.
- Keep scope at exploration only; do not draft PRD or implementation tasks.

## Edge Cases
- Default mode must be explicit and cached; no silent fallback from missing session decision.
- Interactive approval is phase-scoped, so “continue” only advances one delegated phase.
- Proposal-stage uncertainty must route to Grill before `change-new` or PRD/proposal work.
- Auto mode safety language must not blur into interactive wording or imply user pauses.
- Tests must assert concrete contracts and pause points, not keyword presence alone.

## Test Surface
- Review exploration text for exact line references and AI-harness enforcement mapping.
- Later tests should cover mode decision caching, delegated-phase pause behavior, Grill routing, auto gatekeeper checks, and deduped launch logging.

## Risks
- If references stay implicit, later design work may miss the exact gentle-orchestrator contract and drift from intended parity.
- Overloading tests with keyword checks would miss the real behaviors; mitigation is contract-level assertions on mode, pauses, routing, and deduplication.
