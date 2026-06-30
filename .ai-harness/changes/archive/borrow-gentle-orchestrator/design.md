# Design — borrow-gentle-orchestrator

## Context

ai-harness already has a file-backed change workflow, a `change-new` / `change-continue` command split, phase artifacts, and a human review gate before implementation. The gap is conductor discipline: the current `change-orchestrator` prompt and phase prompts leave too much behavior implicit, while gentle-ai's current OpenCode conductor (`gentle-orchestrator`, still sourced from legacy `sdd-orchestrator.md` prompt paths) makes start/resume, stale review, delegation, skill injection, and phase gates explicit.

This design borrows the six confirmed gentle-ai behaviors as contracts around ai-harness's existing workflow. The implementation should deepen the existing change orchestration seam rather than introduce a new orchestrator family, PR-chain behavior, or wholesale state-machine rewrite.

### Design evidence

Preserve these source references in downstream specs, implementation notes, and validator checks so decisions remain traceable:

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

### Contract placement decision

- **Prompt contract** owns agent behavior: start/resume routing language, stale-review invalidation, duplicate-launch refusal, phase result envelope, exact skill-path injection instructions, and auto/interactive gate rules.
- **CLI/state** remains the source of disk authority for change creation/resume and collision/missing-change errors. Add new state only if prompt-only handling cannot enforce a safety invariant across resume or compaction.
- **Renderer metadata** should not become a second state machine. Use it only if exact skill-path or mode values must be rendered from known inputs rather than instructed in prose.
- **Tests/docs** lock behavior. Render tests assert prompt contracts; `tests/test_change.py` changes only when CLI/state behavior changes; `docs/design/change-orchestrator.md` becomes the durable design source for implemented behavior.

## Deep modules

### Start/resume route contract
- Seam: `change-new` / `change-continue` command entry and rendered `change-orchestrator` route instructions.
- Interface: Given a change name and command route, return one of: `start` for a non-existent change created by `change-new`, `resume` for an existing change loaded by `change-continue`, or `blocked` with recovery guidance for collisions, missing changes, or ambiguous route facts. Callers must treat disk state as authoritative and must not infer mode from folder presence inside the prompt.
- Hides: Store lookup details, collision/missing-change wording, legacy prompt ambiguity, and recovery phrasing. The prompt sees a route contract, not raw filesystem heuristics.
- Depth note: Deleting this seam spreads start/resume guessing across prompt text, CLI errors, docs, and tests; keeping it concentrates route authority in one small contract.

### Artifact review ledger
- Seam: Orchestrator review gate over the current phase artifact set under `.ai-harness/changes/{change}/`.
- Interface: Given the current artifact set, last reviewed artifact identity, session continuity status, and phase target, return `approved_current`, `review_required`, or `blocked`. Approval is phase-scoped and artifact-set-scoped: it applies only to the exact reviewed artifact versions for the next permitted phase. Any edit to reviewed artifacts, resume after a session gap, or resume after compaction reopens review before implementation or further gated progression.
- Hides: Artifact fingerprinting strategy, prompt wording for stale approvals, compaction/session-gap detection limits, and how review status is reconstructed from disk artifacts and conversation context.
- Depth note: A small approval status hides the hard part: preventing stale human approval from leaking across changed artifacts, resumed sessions, and phase boundaries.

### Phase result envelope
- Seam: Result block required from `change-explorer`, `change-implementor`, and `change-validator`, consumed by `change-orchestrator` and persisted in phase artifacts.
- Interface: Every phase returns one uniform result block: `status`, `artifacts`, `summary`, `semantic_facts`, and `skills`. `semantic_facts` is the only phase-specific extension point: explorer records budget/follow-up facts, implementor records partial/changed-files facts, validator records verdict/critical-failure facts, and orchestrator-level waiting/blocked facts stay explicit when relevant.
- Hides: Different phase prompt histories, uneven legacy result shapes, fact extraction on resume, and validator-specific severity vocabulary. The orchestrator consumes one envelope and reads semantic facts by name.
- Depth note: One thin envelope replaces several shallow per-phase formats while preserving the few facts orchestration actually needs.

### Delegation launch ledger
- Seam: Session-scoped orchestrator launch log keyed by `(phase, task_fingerprint)` before spawning a subagent.
- Interface: Before delegation, compute a meaningful task fingerprint from phase, target artifacts, and requested work; record launch intent; refuse a second launch with the same key in the same turn/session context unless the fingerprint changes. Refusal returns `blocked` or `waiting` guidance rather than launching duplicate work.
- Hides: Fingerprint normalization, same-turn ambiguity, repeated model output, and recovery when the orchestrator loses conversational memory. Persist this only if prompt/session memory proves insufficient.
- Depth note: The caller learns one rule—no duplicate key—while the implementation handles launch timing, fingerprint construction, and refusal wording.

### Skill-path injection contract
- Seam: Orchestrator-to-subagent instruction handoff for phase skills.
- Interface: For each delegated phase, resolve required skills from the available registry/context and pass exact `SKILL.md` paths in a `Skills to load before work` block. Subagent results report `skills: loaded | fallback | none` plus `skill_resolution` detail when resolution fails or degrades. Do not pass summaries as substitutes for paths; do not invent paths.
- Hides: Registry lookup, legacy hardcoded grill path behavior, fallback wording, and whether skill availability comes from renderer metadata or runtime context.
- Depth note: Exact path injection is a small handoff surface that hides brittle registry/path mechanics and prevents downstream agents from guessing.

### Auto/interactive phase gate
- Seam: Orchestrator phase-transition gate between exploration, design/spec/task artifacts, implementation, and validation.
- Interface: Establish a stable session mode: `interactive` pauses at phase gates for user review, especially before implementation; `auto` may continue only after prior phase success, fresh approval where required, and no blocked semantic facts. Mode is chosen from the command/profile context or explicit user instruction and remains stable for the session; persist only if resume correctness requires it.
- Hides: Profile-specific behavior, cached mode source, gate ordering, and prompt wording that distinguishes review-needed from blocked/failed states.
- Depth note: One gate decision hides phase progression complexity and prevents implementation from starting merely because an earlier phase produced artifacts.

## Internal collaborators

- **Artifact fingerprint helper**: Internal helper behind the artifact review ledger. It identifies the artifact set approved for a phase. It is not a public test seam unless persisted fingerprints are added; render tests and workflow tests cover it through stale-review behavior.
- **Semantic fact normalizer**: Internal prompt/docs convention behind the phase result envelope. It maps legacy facts (`budget`, `partial`, `verdict`, `critical`, `waiting`, `blocked`) into the shared `semantic_facts` shape. It should be tested through rendered phase prompts and validator expectations, not mocked as a separate public seam.
- **Task fingerprint helper**: Internal helper behind the delegation launch ledger. It normalizes phase/task/artifact identity for duplicate detection. If implemented only in prompt text, tests lock the contract wording; if implemented in state, `tests/test_change.py` covers collision/refusal semantics.
- **Skill resolver**: Internal collaborator behind skill-path injection. It may be prompt-only from available skill context or renderer-assisted metadata, but the public seam is exact path injection plus `skill_resolution` reporting.
- **Mode source reader**: Internal collaborator behind the auto/interactive gate. It reads command/profile/user context and exposes a stable session mode to the orchestrator contract.

## Seam map

```text
change-new/change-continue
  -> Start/resume route contract
  -> Auto/interactive phase gate
      -> Artifact review ledger
          -> Delegation launch ledger
              -> Skill-path injection contract
                  -> Phase subagent
                      -> Phase result envelope
                          -> Orchestrator resume/gate decision
```

Phase-scoped approval interaction:

- Exploration/design/spec/task artifacts can be reviewed for the next phase only as a specific artifact set.
- If any reviewed artifact changes, approval becomes stale for the dependent phase and review reopens.
- Resume after compaction or a session gap must re-check approval. If current artifact identity cannot be proven to match the reviewed set, treat it as `review_required`, not approved.
- Interactive mode always pauses before implementation even when artifacts exist; auto mode may continue only when the artifact review ledger says the current set is approved or the phase does not require human review.
- Validator must reject flows where implementation begins from ambiguous route state, stale approval, missing semantic facts, duplicate same-key launch, guessed skill paths, or unstable mode.

## Rejected alternatives

- **PR-chain / `chained-pr` behavior**: Rejected. The change is about file-backed ai-harness orchestration discipline, not adopting gentle-ai PR-chain mechanics. Adding PR-chain behavior would widen scope and blur the local artifact workflow.
- **Rename or migration of `sdd-orchestrator.md` / orchestrator family**: Rejected. gentle-ai source names are evidence only. This change borrows behaviors into `change-orchestrator`; it does not perform naming migration.
- **Full rewrite of the orchestrator or state machine**: Rejected. Existing ai-harness change commands, artifacts, and review gate already provide the backbone. Replace only shallow contracts that leak ambiguity.
- **Prompt-only limitation**: Rejected. Most behavior should start as prompt/docs/render-test contracts, but CLI/state support is allowed when correctness needs disk-backed authority across resume, compaction, or duplicate launch recovery.
- **Renderer metadata as hidden orchestration state**: Rejected. Metadata may supply exact known values, but it must not become a parallel phase machine competing with disk-backed change state.
- **Separate result formats per phase**: Rejected. Phase-specific facts belong under `semantic_facts`; separate envelopes recreate the current shallow seams and make resume/validation harder.

## Validator expectations

- Verify the design evidence references above remain present in design/docs or implementation notes so every borrowed behavior is traceable.
- Verify rendered `change-orchestrator` text states explicit start/resume routing, disk authority, stale artifact invalidation, duplicate-launch refusal, exact skill-path injection, and auto/interactive phase gates.
- Verify rendered phase prompts share one result envelope and preserve semantic facts for exploration budget, implementation partial state, validation verdict, critical validation failure, and waiting/blocked states where applicable.
- Verify implementation does not add PR-chain behavior, rename/migrate orchestrator files for its own sake, or rewrite the state machine wholesale.
- Verify implementation pauses before implementation in interactive mode, and never proceeds from stale approval, ambiguous resume/start state, missing current artifacts, duplicate same-key delegation, or guessed skill paths.
- Verify any CLI/state additions have targeted `tests/test_change.py` coverage; otherwise render tests and docs must be sufficient to lock prompt-only contracts.
