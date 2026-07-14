# Exploration — add-verifiable-receipts

## Budget
430

## Affected Files
- `src/ai_harness/modules/harness/receipts.py` — new deep module for canonical candidate identity, length-delimited hashing, deterministic gate execution records, strict receipt validation, and atomic receipt persistence.
- `src/ai_harness/modules/harness/change.py` — make archive preflight require a current final receipt, recompute candidate identity immediately before the move, and preserve existing sliced and legacy structural checks.
- `src/ai_harness/commands/change.py` — add a thin receipt/recheck command adapter only if the design confirms that the validator needs a native operation to record gate facts.
- `src/ai_harness/main.py` — register the additive receipt command if introduced.
- `src/ai_harness/resources/change-agent/change-validator.md` — keep verdict judgment with the validator but require it to invoke the native recorder for declared validation gates and include the resulting receipt reference in final validation.
- `src/ai_harness/resources/change-agent/change-archiver.md` — require the native pre-archive recheck; the archiver must surface a stale or invalid receipt rather than reinterpreting validator judgment.
- `tests/test_receipts.py` — cover canonical serialization, candidate and output hashing, schema validation, atomic writes, gate-result immutability, stale detection, and failure diagnostics.
- `tests/test_change.py` and `tests/test_change_sliced_archive.py` — prove legacy and sliced archive behavior remains compatible while rejecting missing, malformed, failed, stale, or candidate-mismatched receipts before any move.
- `tests/test_renderers.py` — lock validator/archiver rendered instructions and shared-envelope compatibility when prompt resources change.

## Plan
- Define the receipt contract before implementation: a versioned JSON receipt stored under the active change, containing a deterministic candidate identity, final-validation artifact hash, ordered gate commands, exit status, stdout/stderr output digests (and retained bounded outputs or referenced immutable output files), and an overall native fact result. The validator's release verdict remains separate, human/model judgment.
- Small first slice: support only the root final-validation-to-archive path for both legacy and fully completed sliced changes. Do not receipt per-task, per-slice, implementation approval, remote attestation, signatures, or generalized provenance in this change.
- Implement a single receipt store that canonicalizes JSON, validates the complete schema fail-closed, hashes bytes with explicit labels/length delimiters, and writes a fresh receipt atomically. Capture candidate identity from repository state using a documented native mechanism; include enough tracked/untracked/dirty-state data to reject a changed candidate rather than treating a commit SHA alone as sufficient.
- Expose a narrow native operation for recording deterministic gate facts. It must execute only the gate commands supplied by the validator/orchestrator contract, capture exit code and output deterministically, and never infer pass/fail from validator prose.
- Extend archive preflight to load and validate the receipt, verify all recorded gates passed, recompute the candidate identity and final-validation hash immediately before archive, and reject any mismatch before specs promotion or folder movement. Recheck must not mutate a previously issued receipt.
- Update validator and archiver resources to make the handoff explicit: validator judges requirements and selects/runs required gates; native receipt machinery records and verifies executable facts; archiver invokes recheck immediately before archive and does not rerun or reinterpret gates.
- Add focused unit, lifecycle, CLI, and renderer tests; retain the existing task-completion, continuation-approval, final-validation freshness, destination-collision, and rollback tests unchanged.

## Edge Cases
- A clean `HEAD` is not enough when working-tree changes affect the candidate; candidate identity must distinguish staged, unstaged, untracked, and ignored-policy cases defined by the design.
- A final `validation.md`, relevant source file, task store, PRD, approval, or receipt input changed after gate capture must invalidate the receipt; timestamp-only freshness is insufficient.
- Gate output can be large, binary, nondeterministic, or contain secrets. Define bounded capture, byte hashing, redaction policy, and whether the immutable evidence is stored inline or as receipt-owned files before implementation.
- A gate command can pass while the validator issues a failing judgment, or fail while validator prose claims pass. Archive must require both the existing semantic policy and native all-gates-pass facts without letting either substitute for the other.
- Receipt schema corruption, duplicate gate names, reordered records, unsupported schema versions, missing output evidence, interrupted writes, and subprocess launch failures must fail closed.
- Existing legacy changes and sliced changes without a receipt need clear migration behavior: they remain routable under current flow but cannot archive once the receipt gate is enabled; slice validations and continuation approvals remain independent of the first receipt scope.
- Archive recheck must occur after all prior preflight checks and before the first filesystem move; a post-recheck mutation remains a race outside single-process guarantees and should be documented rather than silently claimed safe.

## Test Surface
- Receipt module tests for canonical byte encoding, stable hashes, atomic persistence, malformed JSON/schema rejection, immutable gate records, output digest verification, and candidate mismatch diagnostics.
- Subprocess-facing tests using controlled commands for pass, non-zero exit, missing executable, stdout/stderr capture, output-size boundary, and deterministic record ordering.
- Archive tests for each mode: valid receipt archives; no receipt, failed gate, edited validation, changed candidate, tampered output/receipt, and recheck-before-move failures leave source/specs untouched.
- Regression tests for existing legacy archive success and sliced continuation/final-validation guards, proving receipt enforcement adds a terminal fact gate rather than changing routing, task association, or approval semantics.
- Renderer tests for validator judgment versus native-fact ownership and archiver immediate-recheck instructions; run repository `uv`/ruff/pytest gates.

## Risks
- Candidate identity is the principal design risk: a commit hash alone cannot bind uncommitted work, while hashing the whole repository may include irrelevant or secret files. Mitigate with an explicit, versioned candidate-input policy and tests for staged/unstaged/untracked boundaries.
- Executing validator-specified commands introduces command-injection, environment, and reproducibility concerns. Mitigate by keeping command selection outside the receipt writer, recording argv/cwd/environment policy canonically, avoiding shell interpolation, and scoping v1 to local execution facts rather than reproducible builds.
- Immutable evidence conflicts with a writable change directory. Mitigate by treating every receipt as append-only content-addressed evidence and making archive accept only the latest valid receipt bound to the current candidate; do not overwrite prior evidence.
- Prompt-only enforcement would be forgeable, while overloading the current archive preflight can blur semantic and deterministic responsibilities. Mitigate with one receipt module and a narrow archive verification seam.
- Requiring receipts may block in-flight changes. Mitigate with an explicit rollout boundary and compatibility decision in design; do not silently waive the archive check based on legacy mode.

## Semantic Facts
- budget: 430
- follow_up: Set the candidate identity boundary, receipt JSON schema and output-retention/redaction policy; decide the exact native command/API and rollout rule for existing in-flight Changes; define how the current semantic verdict/critical gate is machine-read before archive.
