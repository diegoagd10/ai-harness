# Exploration — borrow-gentle-orchestrator

## Summary
gentle-ai’s `gentle-orchestrator` has a much sharper OpenCode contract than ai-harness’s current `change-orchestrator`: explicit start vs resume routing, stale-review re-open rules, session launch deduplication, registry-driven skill-path injection, and an `auto` vs `interactive` phase gate. ai-harness already has the disk-backed state machine and a human review gate, but the current prompt surface is thinner and the phase result contracts are uneven.

## Source evidence references
- gentle-ai:internal/assets/opencode/sdd-orchestrator.md:3-25, 98-108, 182-220, 299-327, 331-391
- gentle-ai:docs/opencode-profiles.md:11-12, 64-66, 124-182
- gentle-ai:docs/intended-usage.md:68-74, 86-90
- gentle-ai:internal/skillregistry/registry.go:231-247
- gentle-ai:internal/cli/run_integration_test.go:2062-2075
- ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:3-29, 30-56, 58-108, 110-166
- ai-harness:docs/design/change-orchestrator.md:23-29, 47-63, 109-156, 173-258, 260-316, 394-423, 435-552
- ai-harness:src/ai_harness/resources/change-agent/change-explorer.md:1-56
- ai-harness:src/ai_harness/resources/change-agent/change-implementor.md:1-61
- ai-harness:src/ai_harness/resources/change-agent/change-validator.md:1-79
- ai-harness:src/ai_harness/modules/harness/change.py:45-89, 135-175
- ai-harness:tests/test_renderers.py:308-423, 1285-1307
- ai-harness:tests/test_change.py:19-57, 78-123, 126-157

## Borrow target analysis

### 1) Sharper start/resume contract
- gentle-ai: start/resume is explicit: `change-new` for Start, `change-continue` for Resume, disk is authoritative, and guessing folder presence is rejected.
- ai-harness already has the command split and explicit store errors, but the prompt still reads like a loose mode classifier.
- Likely change surface: prompt + docs + tests. CLI/state already exists.

### 2) Stale artifact invalidation + re-review
- gentle-ai ties approval to the reviewed artifact set, re-opens on artifact edits, and re-prompts after session gaps/compaction.
- ai-harness already has a human review gate and artifact-path naming, but current wording is narrower and does not yet mirror the “same artifact set only” / “resume re-prompts” discipline as strongly.
- Likely change surface: prompt + docs + render tests.

### 3) Uniform per-phase subagent result contract with semantic facts
- gentle-ai uses one thin result envelope for every subagent, then adds semantic facts only where needed (`budget` for explore, `verdict`/`critical` for validate).
- ai-harness currently has three different phase contracts: explorer has `budget`, validator has `verdict`/`critical`, implementor has `partial`, orchestrator has `waiting`/`blocked`.
- Likely change surface: all change-agent prompts + docs + tests. No obvious CLI/state change unless we decide to surface semantic facts in `ChangeStatus` later.

### 4) Duplicate-launch guard
- gentle-ai keeps a session-scoped `(phase, task-fingerprint)` launch log and refuses duplicate delegation in one turn.
- ai-harness has no equivalent guard in the change-orchestrator prompt.
- Likely change surface: prompt + tests. State mechanics only if we decide prompt memory is not enough.

### 5) Exact skill-path injection discipline
- gentle-ai requires registry lookup, exact `SKILL.md` paths, and a `skill_resolution` feedback loop after delegation.
- ai-harness currently only hardcodes one grill skill path in the orchestrator prompt; no registry-driven “pass exact paths to subagents” contract is present in the change flow.
- Likely change surface: prompt + docs + tests. Renderer metadata probably unchanged unless we want to advertise skill resolution in frontmatter.

### 6) Auto vs interactive phase gate matching gentle-ai behavior
- gentle-ai distinguishes cached `auto` vs `interactive`, with a gatekeeper between phases and a user prompt before advancing in interactive mode.
- ai-harness has a human review gate before `change-implementor`, but no explicit mode split or phase-by-phase interactive gate policy.
- Likely change surface: prompt + docs + tests. CLI/state only if we choose to persist mode; not required by current ai-harness mechanics.

## Current ai-harness gaps
- `change-orchestrator.md` has a good start, but the mode contract is weaker than gentle-ai’s explicit start/resume split.
- The human review gate already exists, but stale-review reopening and resume-after-gap behavior need stronger wording.
- Result contracts are not uniform across `change-explorer`, `change-implementor`, `change-validator`, and `change-orchestrator`.
- No duplicate-launch guard exists for same-turn repeated delegation.
- No registry-backed exact skill-path injection contract exists in the change flow.
- No `auto`/`interactive` gate mode exists for the change pipeline.

## Candidate implementation plan
- Tighten `src/ai_harness/resources/change-agent/change-orchestrator.md` first: start/resume, stale-review invalidation, duplicate-launch guard, skill-path discipline, and auto/interactive gate text.
- Normalize phase result contracts in `change-explorer.md`, `change-implementor.md`, and `change-validator.md` so every phase returns the same thin block plus phase-specific semantic facts.
- Update `docs/design/change-orchestrator.md` to match the new contract and make downstream specs/tasks easier to derive.
- Add or extend render tests in `tests/test_renderers.py` to lock the borrowed contract wording and the new result envelope.
- Only touch `tests/test_change.py` / `src/ai_harness/modules/harness/change.py` if we decide the new contract needs persisted CLI/state fields; current read suggests that is optional.

## Budget
280

## Affected Files
- src/ai_harness/resources/change-agent/change-orchestrator.md — main prompt contract changes
- src/ai_harness/resources/change-agent/change-explorer.md — normalize result contract
- src/ai_harness/resources/change-agent/change-implementor.md — normalize result contract
- src/ai_harness/resources/change-agent/change-validator.md — normalize result contract
- docs/design/change-orchestrator.md — durable design/spec source
- tests/test_renderers.py — lock rendered prompt contract and result wording
- tests/test_change.py — only if CLI/state semantics change
- src/ai_harness/modules/harness/change.py — only if semantic facts move into derived state

## Plan
- Compare current prompt sections against gentle-ai’s start/resume, gate, dedup, and skill-resolution blocks.
- Patch change-agent prompts first, keeping CLI/state untouched unless a missing invariant cannot be expressed in prompt text.
- Refresh design docs and render tests in the same slice so the new contract is test-locked.
- Re-check whether any state fields need to be added after prompt changes land.

## Edge Cases
- Resume after compaction/session gap should re-open review even if artifacts look unchanged.
- Same-turn duplicate delegation should not launch a second subagent for the same phase/task fingerprint.
- Missing skill registry should fall back cleanly and still report a `skill_resolution` state.
- Explorer/validator semantic facts must remain recoverable from artifact prose on resume.
- Interactive mode should stop after the gate; auto mode should continue only after a PASS.

## Test Surface
- Rendered `change-orchestrator` body contains start/resume, stale-review, dedup, skill-path, and auto/interactive wording.
- Rendered phase prompts expose a uniform result envelope.
- Existing change status tests still pass for `change-new`/`change-continue` collision and resume errors.
- If CLI/state is extended, add targeted `change` module tests for any new persisted fields.

## Risks
- Prompt-only enforcement can drift if tests stay too shallow; lock exact contract phrases, not just broad themes.
- Uniform result contracts may tempt a larger state-machine rewrite; keep the first slice prompt- and doc-led unless state is truly required.
- Skill-path discipline must match the existing registry model, not workspace-relative paths, or subagents will load the wrong files.
- Auto/interactive semantics can become ambiguous unless the mode source is explicit and cached for the session.
