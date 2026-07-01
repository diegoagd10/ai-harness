# PRD — borrow-gentle-orchestrator

## Intent

Borrow the proven conductor discipline from gentle-ai’s current OpenCode `gentle-orchestrator` into ai-harness’s file-backed change workflow, without renaming the ai-harness change, rewriting the system, or publishing externally.

The current gentle-ai conductor context is `gentle-orchestrator`, even where source prompt files still retain legacy `sdd-orchestrator.md` naming. That naming migration is explicitly out of scope for this change. The intent is to borrow behavior and contracts, not rename the orchestrator family.

This PRD is a source-context handoff for design, specs, tasks, implementation, and validation. Downstream work should use the source references below as evidence, not as optional background.

## Source References

- gentle-ai `gentle-orchestrator` prompt evidence: `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:3-25, 98-108, 182-220, 299-327, 331-391`
- gentle-ai OpenCode profile/conductor evidence: `gentle-ai:docs/opencode-profiles.md:11-12, 64-66, 124-182`
- gentle-ai intended usage evidence: `gentle-ai:docs/intended-usage.md:68-74, 86-90`
- gentle-ai skill registry evidence: `gentle-ai:internal/skillregistry/registry.go:231-247`
- gentle-ai integration test evidence: `gentle-ai:internal/cli/run_integration_test.go:2062-2075`
- ai-harness current orchestrator prompt evidence: `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:3-29, 30-56, 58-108, 110-166`
- ai-harness durable design evidence: `ai-harness:docs/design/change-orchestrator.md:23-29, 47-63, 109-156, 173-258, 260-316, 394-423, 435-552`
- ai-harness explorer prompt evidence: `ai-harness:src/ai_harness/resources/change-agent/change-explorer.md:1-56`
- ai-harness implementor prompt evidence: `ai-harness:src/ai_harness/resources/change-agent/change-implementor.md:1-61`
- ai-harness validator prompt evidence: `ai-harness:src/ai_harness/resources/change-agent/change-validator.md:1-79`
- ai-harness change state evidence: `ai-harness:src/ai_harness/modules/harness/change.py:45-89, 135-175`
- ai-harness renderer test evidence: `ai-harness:tests/test_renderers.py:308-423, 1285-1307`
- ai-harness change CLI/state test evidence: `ai-harness:tests/test_change.py:19-57, 78-123, 126-157`

## Scope

### In

- Tighten ai-harness change orchestration around six borrowed `gentle-orchestrator` behaviors:
  1. sharper start/resume contract
  2. stale artifact invalidation plus re-review
  3. uniform per-phase subagent result contract with semantic facts
  4. duplicate-launch guard
  5. exact skill-path injection discipline
  6. auto vs interactive phase gate matching gentle-ai behavior
- Update prompt resources, design docs, and render tests needed to lock the borrowed behavior.
- Use CLI/state changes when prompt-only enforcement is insufficient. Prompt-only limitation is not a requirement.
- Preserve ai-harness’s file-backed change workflow and existing human review gate.
- Ensure workflow pauses for user review before implementation begins.

### Out

- PR-chain or `chained-pr` behavior.
- Canonical rename or migration from `sdd-orchestrator.md` naming to another name.
- Full rewrite of the change orchestrator or change state machine.
- External publication, GitHub issue creation, or PR creation.
- Editing product code as part of PRD authoring.

## Capabilities

- Start/resume contract: The orchestrator treats start and resume as explicit routes backed by disk state, not as a loose folder-presence guess.
  - Problem: ai-harness has command split and store errors, but current prompt surface still reads like a soft mode classifier.
  - Desired behavior: `change-new` starts only new changes; `change-continue` resumes only existing changes; disk is authoritative; ambiguity is blocked with clear recovery guidance.
  - Acceptance criteria: Rendered orchestrator prompt states explicit start/resume routing; docs describe disk authority; tests lock collision and missing-change behavior or prompt text; no implementation phase starts from an ambiguous route.
  - Likely affected areas: `src/ai_harness/resources/change-agent/change-orchestrator.md`, `docs/design/change-orchestrator.md`, `tests/test_renderers.py`, possibly `tests/test_change.py` if CLI/state wording changes.
  - Evidence references: `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:3-25`; `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:3-29`; `ai-harness:src/ai_harness/modules/harness/change.py:45-89`; `ai-harness:tests/test_change.py:19-57, 78-123, 126-157`.

- Stale artifact invalidation and re-review: The orchestrator binds approval to the reviewed artifact set and reopens review when artifacts become stale.
  - Problem: ai-harness has a human review gate, but current wording is narrower than gentle-ai’s same-artifact-set and resume-after-gap discipline.
  - Desired behavior: Any edit to reviewed artifacts invalidates prior approval; resume after session gap or compaction re-prompts for review; implementation cannot proceed until the current artifact set is reviewed.
  - Acceptance criteria: Prompt and docs state approval applies only to the exact reviewed artifact set; render tests lock stale-review/reopen wording; implementor path requires review before code changes; resume path rechecks review state.
  - Likely affected areas: `src/ai_harness/resources/change-agent/change-orchestrator.md`, `docs/design/change-orchestrator.md`, `tests/test_renderers.py`.
  - Evidence references: `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:98-108, 182-220`; `gentle-ai:docs/intended-usage.md:68-74, 86-90`; `ai-harness:docs/design/change-orchestrator.md:173-258, 394-423`; `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:58-108`.

- Uniform phase result envelope with semantic facts: Every delegated phase returns the same thin contract plus phase-specific semantic facts.
  - Problem: ai-harness phase prompts currently expose uneven result shapes: explorer has `budget`, validator has `verdict`/`critical`, implementor has `partial`, and orchestrator has `waiting`/`blocked`.
  - Desired behavior: Explorer, implementor, and validator use one uniform result block while preserving semantic facts needed for orchestration: exploration budget, validation verdict, critical failure marker, partial implementation marker, waiting/blocked state as applicable.
  - Acceptance criteria: All phase prompts document one shared result envelope; phase-specific semantic facts are named consistently; render tests cover the envelope across explorer, implementor, and validator; docs explain how semantic facts are recovered on resume.
  - Likely affected areas: `src/ai_harness/resources/change-agent/change-explorer.md`, `src/ai_harness/resources/change-agent/change-implementor.md`, `src/ai_harness/resources/change-agent/change-validator.md`, `src/ai_harness/resources/change-agent/change-orchestrator.md`, `docs/design/change-orchestrator.md`, `tests/test_renderers.py`.
  - Evidence references: `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:299-327, 331-391`; `ai-harness:src/ai_harness/resources/change-agent/change-explorer.md:1-56`; `ai-harness:src/ai_harness/resources/change-agent/change-implementor.md:1-61`; `ai-harness:src/ai_harness/resources/change-agent/change-validator.md:1-79`; `ai-harness:docs/design/change-orchestrator.md:435-552`.

- Duplicate-launch guard: The orchestrator prevents duplicate same-turn delegation for the same phase and task fingerprint.
  - Problem: ai-harness has no equivalent prompt-level guard, so repeated delegation can launch duplicate subagents for the same work.
  - Desired behavior: The orchestrator keeps a session-scoped launch log keyed by `(phase, task-fingerprint)` and refuses to launch the same delegation twice in one turn/session context. If prompt memory is not reliable enough, implementation may add CLI/state support.
  - Acceptance criteria: Prompt defines the launch log and refusal behavior; tests lock duplicate-launch wording or state behavior; validator confirms same phase/task fingerprint cannot be launched twice without a meaningful changed fingerprint.
  - Likely affected areas: `src/ai_harness/resources/change-agent/change-orchestrator.md`, `docs/design/change-orchestrator.md`, `tests/test_renderers.py`, possibly `src/ai_harness/modules/harness/change.py` and `tests/test_change.py` if persisted state is introduced.
  - Evidence references: `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:182-220`; `gentle-ai:internal/cli/run_integration_test.go:2062-2075`; `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:110-166`.

- Exact skill-path injection discipline: The orchestrator resolves skills through the registry and passes exact `SKILL.md` paths to subagents.
  - Problem: ai-harness currently hardcodes one grill skill path and lacks a general registry-driven skill injection contract for the change flow.
  - Desired behavior: For every delegated phase that needs skills, the orchestrator resolves exact `SKILL.md` paths from the available registry/context, injects those paths into subagent instructions, and reports `skill_resolution` outcome after delegation. Missing skills should degrade explicitly rather than silently inventing paths.
  - Acceptance criteria: Prompt requires exact path injection, not summaries or guessed paths; docs define `skill_resolution`; tests lock registry/path wording; subagent contract includes loaded/fallback/none status.
  - Likely affected areas: `src/ai_harness/resources/change-agent/change-orchestrator.md`, phase prompts if they consume skill metadata, `docs/design/change-orchestrator.md`, `tests/test_renderers.py`, possibly renderer metadata if skill resolution must be surfaced in frontmatter.
  - Evidence references: `gentle-ai:internal/skillregistry/registry.go:231-247`; `gentle-ai:docs/opencode-profiles.md:124-182`; `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:331-391`; `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:110-166`.

- Auto vs interactive phase gate: The orchestrator distinguishes auto and interactive progression using gentle-ai-style phase gates.
  - Problem: ai-harness has a human review gate before implementation but no explicit cached `auto` vs `interactive` mode split or phase-by-phase interactive gate policy.
  - Desired behavior: In interactive mode, the workflow pauses for user review before advancing across phase gates, especially before implementation. In auto mode, the workflow may continue only after the prior phase passes and gate conditions are satisfied. The selected mode should be explicit and stable for the session; if prompt memory is insufficient, state may be added.
  - Acceptance criteria: Prompt and docs define auto/interactive mode source, caching, and phase gate behavior; rendered orchestrator includes mandatory pause before implementation in interactive mode; tests cover gate wording; implementation may use CLI/state changes if needed to persist mode.
  - Likely affected areas: `src/ai_harness/resources/change-agent/change-orchestrator.md`, `docs/design/change-orchestrator.md`, `tests/test_renderers.py`, possibly `src/ai_harness/modules/harness/change.py` and `tests/test_change.py` if mode persistence is required.
  - Evidence references: `gentle-ai:docs/opencode-profiles.md:11-12, 64-66`; `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:98-108, 182-220`; `ai-harness:docs/design/change-orchestrator.md:173-258, 260-316, 394-423`; `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:58-108`.

## Approach

- Treat gentle-ai `gentle-orchestrator` behavior as source evidence for contracts and ai-harness files as evidence for current gaps.
- Patch the main orchestrator prompt first because it owns routing, review, duplicate delegation, skill injection, and phase gates.
- Normalize phase prompt result contracts next so downstream specs and validators can reason over one envelope.
- Update `docs/design/change-orchestrator.md` as the durable design source after prompt behavior is clear.
- Add or extend render tests to lock contract wording and prevent prompt drift.
- Only add CLI/state fields when prompt/docs/tests cannot enforce a required invariant reliably. This PRD explicitly permits CLI/state changes if needed.
- Preserve the workflow rule that user review must happen before implementation. Interactive mode must pause before implementation; auto mode still must satisfy gate conditions before proceeding.

## Affected Areas

- `src/ai_harness/resources/change-agent/change-orchestrator.md` — primary conductor contract for start/resume, stale review, duplicate launch, skill-path injection, and auto/interactive gates.
- `src/ai_harness/resources/change-agent/change-explorer.md` — shared result envelope plus exploration semantic facts.
- `src/ai_harness/resources/change-agent/change-implementor.md` — shared result envelope plus implementation semantic facts.
- `src/ai_harness/resources/change-agent/change-validator.md` — shared result envelope plus validation semantic facts.
- `docs/design/change-orchestrator.md` — durable design source for borrowed conductor behavior.
- `tests/test_renderers.py` — prompt rendering assertions for borrowed contracts.
- `tests/test_change.py` — only if CLI/state semantics change.
- `src/ai_harness/modules/harness/change.py` — only if semantic facts, mode, stale review, or duplicate-launch behavior require persisted state.

## Risks

- Prompt-only enforcement can drift unless render tests assert specific contract language and semantic facts.
- Uniform result envelopes can accidentally expand into a state-machine rewrite; keep changes scoped unless state is required for correctness.
- Skill-path injection can become brittle if paths are guessed instead of resolved from the available registry/context.
- Auto vs interactive mode can become unsafe if mode source is implicit or changes mid-session.
- Stale-review invalidation can block too aggressively if it treats unrelated files as reviewed artifacts; approval must bind to the actual artifact set.

## Rollback Plan

- Revert prompt and design-doc changes to the previous ai-harness change-orchestrator contract.
- Remove or relax render assertions that lock the borrowed behavior.
- If CLI/state fields are added, preserve backward compatibility during rollout and provide a small migration or default behavior; rollback by ignoring new fields and restoring previous status derivation.
- Keep this change isolated from product code so rollback does not affect runtime application behavior.

## Dependencies

- Existing ai-harness file-backed change root and artifact naming conventions.
- Existing `change-new` / `change-continue` command split and store error behavior.
- Current change-agent prompt rendering infrastructure.
- Existing human review gate before implementation.
- gentle-ai `gentle-orchestrator` source evidence listed in Source References.
- Skill registry or available skill context sufficient to resolve exact `SKILL.md` paths, or an explicit fallback path when unavailable.

## Success Criteria

- PRD, design, specs, tasks, implementor, and validator can trace each borrowed behavior to concrete gentle-ai and ai-harness evidence.
- Rendered orchestrator prompt includes explicit start/resume routing, stale-review invalidation, duplicate-launch guard, exact skill-path injection, and auto/interactive gate behavior.
- Rendered phase prompts share one result envelope and preserve phase-specific semantic facts.
- Tests protect the borrowed conductor contracts from prompt drift.
- Implementation does not borrow PR-chain behavior, perform canonical rename/migration, or rewrite the orchestrator wholesale.
- Workflow pauses for user review before implementation, and no implementation proceeds from stale or unreviewed artifacts.
