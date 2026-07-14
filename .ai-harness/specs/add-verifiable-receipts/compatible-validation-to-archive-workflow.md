# Spec — Compatible validation-to-archive workflow

## Purpose

Expose the native run, semantic write, seal, route, and archive sequence through thin stable CLI and rendered-agent contracts while migrating every active Change without bypasses.

## Requirements

### Requirement: Native gate-run CLI contract
The system MUST provide non-interactive `change-gates-run -c <change> -i '<JSON>'` as a thin adapter from the exact version-1 gate-declaration JSON schema to the receipt module.

#### Scenario: Gate facts are returned
GIVEN a valid declaration request
WHEN the command runs
THEN it emits machine-readable run ID, before/after candidate IDs, aggregate pass fact, and ordered outcome summaries without evidence contents

#### Scenario: Recorded gate failure is not adapter failure
GIVEN execution is recorded completely but one or more gates do not pass
WHEN the command returns
THEN it exits successfully with `all_gates_passed=false`

#### Scenario: Invalid or unsafe operation fails
GIVEN declaration, candidate capture, persistence, schema, or policy validation fails
WHEN the command returns
THEN it exits non-zero with a safe deterministic diagnostic and no fabricated facts

### Requirement: Native seal CLI contract
The system MUST provide non-interactive `change-receipt-seal <change>` accepting no fact-bearing options and returning the derived seal summary.

#### Scenario: Diagnostic denial is sealed
GIVEN inputs are well-formed and current but semantic or native approval is false
WHEN the command seals the receipt
THEN it exits successfully and emits receipt ID, run ID, separate semantic/native booleans, and `archive_eligible=false`

#### Scenario: Stale or malformed binding fails
GIVEN validation, candidate, run, evidence, or storage cannot be validly bound
WHEN the seal command runs
THEN it exits non-zero and does not advance `current`

### Requirement: Thin adapter ownership
The system MUST keep hashing, Git inspection, redaction, validation parsing, gate execution, storage, and eligibility policy inside the receipt module; Typer registration MUST only expose command names and map domain values and errors.

#### Scenario: CLI request attempts to supply facts
GIVEN input includes exit codes, candidate IDs, evidence digests, verdicts, pass values, environment overrides, or receipt IDs
WHEN a producer command parses it
THEN exact-schema validation rejects the input instead of forwarding or honoring those fields

### Requirement: Validator run-write-seal guidance
The rendered validator instructions MUST require the validator to declare and run the complete ordered final gates natively, inspect returned facts, write root `validation.md` with the exact `gate-run`, then seal once without post-seal edits.

#### Scenario: Validator follows an approving flow
GIVEN final requirements and gates support release
WHEN the validator completes root validation
THEN the rendered protocol keeps semantic judgment in `verdict` and `critical`, references the native run, seals it, and reports the receipt

#### Scenario: Validator observes gate failure
GIVEN a native gate does not pass
WHEN the validator writes its judgment
THEN instructions prohibit claiming native success or hand-authoring evidence and allow a non-eligible diagnostic result

### Requirement: Archiver single-call guidance
The rendered archiver instructions MUST direct the archiver to invoke only the existing native `change-archive` operation and surface its exact safe failure without rerunning gates, resealing, moving files directly, or reinterpreting verdicts.

#### Scenario: Archive call fails verification
GIVEN `change-archive` reports a stale or invalid receipt
WHEN the archiver responds
THEN it reports the failure verbatim as actionable guidance and performs no retry or manual move

### Requirement: Terminal routing guidance
The system MUST keep normal legacy and sliced routing behavior but MUST route an otherwise terminal Change lacking current authorization back to `validate` for legacy or `final-validate` for sliced with an actionable blocked reason.

#### Scenario: Root validation exists without a receipt
GIVEN an otherwise complete active Change has old root validation but no current receipt
WHEN `change-continue` derives the next action
THEN it requests the mode-appropriate final validation action rather than archive

#### Scenario: Prior status claimed archive readiness
GIVEN cached or caller-provided status says a Change is ready to archive
WHEN direct archive runs
THEN it recomputes structural and receipt state from disk and does not trust the prior status

### Requirement: Fail-closed active-Change migration
The system MUST require every active legacy and sliced Change to perform a fresh native run, semantic validation write, and seal after rollout, with no timestamp cutoff, compatibility flag, waiver, manually authored receipt, or legacy exception.

#### Scenario: In-flight Change predates rollout
GIVEN an active Change has readable pre-receipt artifacts
WHEN it continues through the workflow
THEN existing artifacts remain routable but archive remains blocked until the new protocol succeeds

#### Scenario: Change is already archived
GIVEN a Change was archived before rollout
WHEN the new workflow is enabled
THEN it is neither read for receipt enforcement nor migrated or rewritten

### Requirement: Shared envelope and toolchain compatibility
The system MUST preserve existing shared result envelopes and archive success/error contracts and MUST remain compatible with Python 3.12 or newer, `uv`, Typer, questionary-based existing flows, ruff, pytest, Docker/bash end-to-end execution, and pnpm/TypeScript renderer harnesses.

#### Scenario: Receipt operations run non-interactively
GIVEN receipt commands are invoked from Typer directly or through a Docker/bash harness
WHEN no interactive terminal is available
THEN they do not invoke questionary and produce the same JSON/result contracts

#### Scenario: Rendered contracts are consumed cross-language
GIVEN the pnpm/TypeScript harness renders validator and archiver resources
WHEN fixtures are compared
THEN the run/write/seal sequence, exact `gate-run` field, judgment/fact separation, and single archive call are stable

### Requirement: Isolated workflow verification
The system SHOULD cover unit, CLI, renderer, legacy lifecycle, sliced lifecycle, rollback, and end-to-end behavior using temporary repositories and controlled local subprocesses; tests MUST NOT touch the user system or depend on network services.

#### Scenario: Repository gates validate the workflow
GIVEN the focused receipt and lifecycle tests pass
WHEN the project runs its declared `uv`, ruff, pytest, Docker/bash, and pnpm/TypeScript checks as applicable
THEN producer, renderer, router, and archive contracts pass without mocks beyond HTTP clients, databases, or file persistence boundaries
