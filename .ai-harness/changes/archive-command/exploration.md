# Exploration — archive-command

## Budget
25

## Affected Files
- src/ai_harness/resources/change-agent/change-orchestrator.md — add explicit archive command contract and semantics.
- docs/design/change-orchestrator.md — keep prompt wording aligned with archive gate / local move behavior.
- tests/test_renderers.py — update prompt-content assertions if archive wording or resource set changes.

## Plan
- Lift archive behavior from design into orchestrator prompt as a first-class command contract.
- Make semantic gate explicit: archive only after validator pass / pass-with-warnings with zero critical.
- Verify rendered prompt tests still describe the expected archive contract and file set.

## Edge Cases
- `validation.md` exists but `critical > 0` — archive stays blocked.
- `pass-with-warnings` is allowed only when critical count is zero.
- Pending tasks still block archive even after validation passed.
- Archive must remain a local file move; no git/branch/PR side effects.

## Test Surface
- `tests/test_renderers.py` prompt-body assertions for change-orchestrator.
- Resource-set assertions if a new archive prompt file is introduced later.
- Manual render check for `change-orchestrator.md` body consistency.

## Risks
- Prompt/design drift if archive wording is updated in one place only; mitigate by mirroring design source.
- Overloading archive with execution details that belong in validator/state docs; keep contract narrow.
- Resource discovery churn if archive becomes a separate prompt file; confirm renderer expectations before landing.
