# Spec — artifact invalidation + re-review

## Purpose

Bind human approval to the exact reviewed artifact set and reopen review after stale artifacts, session gaps, or compaction before gated progression.

Traceability: PRD capability “Stale artifact invalidation and re-review”; design seam “Artifact review ledger”; evidence `gentle-ai:internal/assets/opencode/sdd-orchestrator.md:98-108, 182-220`, `gentle-ai:docs/intended-usage.md:68-74, 86-90`, `ai-harness:docs/design/change-orchestrator.md:173-258, 394-423`, `ai-harness:src/ai_harness/resources/change-agent/change-orchestrator.md:58-108`.

## Requirements

### Requirement: Approval is artifact-set scoped
The system MUST apply approval only to the exact reviewed artifact versions for the next permitted phase.

#### Scenario: Current reviewed artifacts permit next phase
GIVEN the user reviewed the current artifact set
WHEN the orchestrator evaluates the next permitted phase
THEN approval is treated as current for that exact artifact set

#### Scenario: Different artifact set requires review
GIVEN approval exists for one artifact set
WHEN the current artifact set differs from the reviewed set
THEN the system treats approval as stale and requires re-review

### Requirement: Artifact edits invalidate approval
The system MUST invalidate prior approval when any reviewed artifact is edited before its dependent gated phase completes.

#### Scenario: Reviewed design changes before implementation
GIVEN design/spec/task artifacts were reviewed for implementation
WHEN any reviewed artifact is edited
THEN implementation remains blocked until the changed artifact set is reviewed again

#### Scenario: Unrelated file does not stale reviewed set
GIVEN approval is bound to a specific artifact set
WHEN an unrelated file outside that reviewed set changes
THEN the system does not invalidate approval solely because of that unrelated change

### Requirement: Resume rechecks review state
The system MUST re-prompt for review after a session gap or compaction when current artifact identity cannot be proven to match the reviewed set.

#### Scenario: Resume after gap reopens review
GIVEN a change resumes after a session gap
WHEN the orchestrator cannot prove the current artifact set matches the reviewed set
THEN it reports `review_required` instead of assuming approval

#### Scenario: Resume after compaction reopens review
GIVEN context was compacted before resuming a change
WHEN prior review state cannot be reconstructed safely
THEN gated progression pauses for user review

### Requirement: Implementation requires current review
The system MUST NOT start implementation from stale, missing, or unreviewed artifacts.

#### Scenario: Stale approval blocks implementor
GIVEN approval was invalidated by artifact changes
WHEN the workflow reaches the implementation gate
THEN no implementor delegation starts until the user reviews the current artifact set

#### Scenario: Missing artifacts block implementor
GIVEN required pre-implementation artifacts are missing
WHEN the workflow reaches the implementation gate
THEN implementation is blocked with guidance to create or recover the missing artifacts

### Requirement: Regression coverage for stale review
The system SHOULD include render or state tests that lock stale-review wording and re-review behavior.

#### Scenario: Render test locks same-artifact-set language
GIVEN renderer tests execute
WHEN `change-orchestrator` is rendered
THEN assertions cover exact artifact-set approval, invalidation on edits, and resume re-review

#### Scenario: State tests cover persisted review fields if added
GIVEN implementation adds persisted review fingerprints or review status
WHEN change module tests execute
THEN tests cover stale approval and current approval outcomes
