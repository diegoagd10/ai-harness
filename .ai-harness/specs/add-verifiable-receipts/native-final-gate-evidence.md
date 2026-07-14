# Spec — Native final-gate evidence

## Purpose

Produce deterministic, auditable native facts for an ordered set of final gates against one exact repository candidate, without accepting caller-authored outcomes or persisting unredacted output.

## Requirements

### Requirement: Canonical typed objects
The system MUST encode persisted candidate and gate-run objects as canonical UTF-8 JSON with exact versioned schemas and MUST derive lowercase SHA-256 identifiers with object-specific labels and explicit length delimiters.

#### Scenario: Equivalent input is deterministic
GIVEN identical candidate manifests, gate records, and retained evidence bytes
WHEN two gate-run bundles are produced
THEN their canonical object bytes and typed identifiers are byte-identical

#### Scenario: Non-canonical or ambiguous input is rejected
GIVEN an object with duplicate or unknown keys, unsupported schema or policy, non-canonical bytes, a float, or an invalid typed identifier
WHEN the object is read
THEN verification fails closed rather than normalizing or accepting it

### Requirement: Declaration-only boundary
The system MUST accept one through 64 ordered gate declarations containing only a valid unique gate ID, non-empty bounded argv array, confined repository-relative cwd, and integer timeout from 1 through 3600 seconds.

#### Scenario: Valid declaration is accepted
GIVEN a version-1 request with unique IDs, direct argv arrays, in-repository working directories, and valid timeouts
WHEN the native runner validates the request
THEN it launches each declaration exactly once in declaration order

#### Scenario: Invalid declaration launches nothing
GIVEN a request with no gates, duplicate or invalid IDs, empty or oversized argv, a boolean or out-of-range timeout, an absolute or traversing cwd, a symlink escape, or an unsupported field or version
WHEN the native runner validates the request
THEN it reports `declaration.invalid` or the applicable policy error, launches no process, and publishes no run

### Requirement: Secret-safe process invocation
The system MUST invoke each gate directly with `shell=False`, closed stdin, a fresh process group, one snapshot of the versioned inherited environment, and no caller-controlled native fact or environment field.

#### Scenario: Arguments are not shell-interpreted
GIVEN an argv element containing shell metacharacters
WHEN the gate is run
THEN the element is passed literally to the declared executable and no implicit shell command is executed

#### Scenario: Secret value in argv is rejected
GIVEN an argv element containing an exact non-empty value classified as secret by the inherited-environment policy
WHEN the declaration is validated
THEN the complete request is rejected before launch without persisting or reporting the argument or secret value

### Requirement: Complete outcome recording
The system MUST attempt later gates after an ordinary gate failure and MUST derive launch, termination, return-code, per-gate pass, and aggregate pass facts from observed execution.

#### Scenario: All gates pass
GIVEN every declared process launches, exits normally with code zero, remains within timeout and output limits, and the candidate remains stable
WHEN the run completes
THEN every gate has `passed=true` and the run has `all_gates_passed=true`

#### Scenario: Gate failure remains diagnosable
GIVEN a gate exits non-zero, is not found, lacks permission, raises an OS launch error, times out, or overflows output
WHEN the run completes without an infrastructure failure
THEN its deterministic failure outcome is retained, later gates are attempted, and `all_gates_passed` is false

#### Scenario: Infrastructure failure aborts publication
GIVEN trustworthy candidate capture, process observation, or bundle persistence cannot be completed
WHEN the runner handles the failure
THEN it raises a stable safe error and does not publish a gate run as complete

### Requirement: Candidate identity boundary
The system MUST bind Git HEAD or unborn state, all index entries, tracked worktree bytes/types/modes/deletions, recursive submodule state, and every non-ignored untracked path in sorted canonical records.

#### Scenario: Relevant repository state changes identity
GIVEN a captured candidate
WHEN HEAD, conflict stage, staged content, unstaged content, deletion, executable mode, symlink target, submodule state, or non-ignored untracked content changes
THEN the candidate identifier changes and diagnostics identify the first changed category and path without exposing content

#### Scenario: Defined exclusions do not change identity
GIVEN only `.git/`, a Git-ignored path, the target Change's root `validation.md`, or the target Change's `.receipts/` namespace changes
WHEN the same target Change is captured again
THEN its candidate identifier is unchanged by that excluded state

#### Scenario: Other Change data remains in scope
GIVEN a source, configuration, task, approval, slice validation, sibling Change, or other non-ignored untracked path changes
WHEN candidate identity is recaptured
THEN the candidate identifier changes

### Requirement: Fail-closed candidate capture
The system MUST reject unsupported or unstable filesystem and Git observations rather than omit them or retry until they appear stable.

#### Scenario: Unsupported candidate input fails
GIVEN an invalid UTF-8 Git path, unreadable file, special file, escaping symlink, repository-boundary or submodule-cycle violation, Git inspection error, or observable read race
WHEN candidate capture runs
THEN capture fails with a safe category/path diagnostic and no successful candidate is returned

#### Scenario: Consecutive manifests disagree
GIVEN repository state changes between the two required consecutive manifest captures
WHEN candidate capture completes
THEN it reports capture failure instead of selecting either manifest

### Requirement: Before-and-after candidate binding
The system MUST capture the candidate before the first gate and after the last gate and MUST make unequal identities non-passing.

#### Scenario: Gate mutates candidate
GIVEN a gate exits zero but changes an in-scope repository path
WHEN the run is finalized
THEN the run retains both candidate manifests, reports candidate mutation, and has `all_gates_passed=false`

### Requirement: Redacted bounded evidence
The system MUST persist only deterministic binary-safe redacted stdout and stderr, each with a 1 MiB raw-observed and redacted-retained limit, typed digest, retained length, completeness, policy ID, and replacement count.

#### Scenario: Known secrets are redacted across chunks
GIVEN output contains overlapping secret-classified inherited values, including a value split across read chunks
WHEN evidence is retained
THEN longest-first bytewise replacement writes `<redacted:secret>`, records the deterministic replacement count, and writes no raw bytes or raw-output digest

#### Scenario: Empty and binary streams are retained exactly
GIVEN a gate emits empty stdout and arbitrary non-text stderr within both limits
WHEN evidence is published
THEN regular evidence files exist for both streams and their recorded byte lengths and digests match the retained bytes without text decoding

#### Scenario: Output exceeds a limit
GIVEN either stream exceeds its raw or retained limit
WHEN the executor observes overflow
THEN it terminates the process group, retains only the bounded redacted prefix with `complete=false`, and marks the gate non-passing

### Requirement: Immutable atomic run bundles
The system MUST publish complete content-addressed run bundles atomically, MUST never overwrite an existing object, and MAY reuse an exact existing object only after complete byte and transitive evidence verification.

#### Scenario: Publication is interrupted
GIVEN interruption occurs before the temporary bundle is atomically renamed
WHEN runs are later enumerated or verified
THEN orphan temporary data is ineligible and no partial run is accepted

#### Scenario: Evidence is tampered
GIVEN evidence is missing, symlinked, non-regular, has a mismatched length or digest, uses an unknown redaction policy, or the bundle contains undeclared files
WHEN the run is verified
THEN verification fails closed and the run cannot support archive eligibility

### Requirement: Isolated executable tests
The system SHOULD verify process and candidate behavior with controlled argv subprocesses and temporary real Git repositories and MUST NOT run tests against or modify the user's repository, home configuration, credentials, or external services.

#### Scenario: Test suite exercises platform contracts
GIVEN Python 3.12 or newer under `uv`
WHEN receipt tests run with pytest and repository linting runs with ruff
THEN no shell, network, database, or user-system fixture is required and subprocess effects remain inside temporary directories
