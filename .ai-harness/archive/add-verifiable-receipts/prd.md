# PRD — add-verifiable-receipts

## Intent

Make root final validation an auditable archive authorization rather than a prompt-only handoff. A native, deterministic receipt must bind the exact candidate, immutable facts and retained evidence from the declared validation gates, and the exact root `validation.md`. Archive remains authorized only when the validator's semantic judgment approves release **and** every natively recorded gate passed, followed by a current-state recheck immediately before the first archive move.

## Scope

### In

- Root final validation through archive for legacy Changes and sliced Changes whose capabilities, tasks, validations, and continuation approvals are already complete.
- A versioned, content-addressed gate-run and receipt format, canonical hashing, bounded redacted output evidence, atomic persistence, and a narrow native run/seal protocol.
- Machine-readable semantic approval from root `validation.md`, kept distinct from native executable facts.
- Candidate capture before and after gate execution and immediate candidate, validation, receipt, and evidence recheck during archive preflight.
- Strict failure behavior, migration rules for active Changes, prompt/CLI integration, and focused lifecycle, integrity, and renderer coverage.

### Out

- Receipts for implementation, tasks, individual capabilities, slice validations, continuation approvals, or non-final validation.
- Gate discovery or interpretation of `CODING_STANDARDS.md` in product code; the validator/orchestrator remains responsible for declaring the required ordered gates.
- Remote execution, signatures, trusted timestamps, key management, third-party attestation, reproducible-build claims, SBOMs, or generalized provenance.
- A command sandbox or permission system. The native runner removes shell interpolation and constrains metadata paths, but declared executables retain the validator process's operating-system permissions.
- Concurrent-writer guarantees or closure of the mutation race after the final recheck begins. v1 guarantees one-process ordering only.
- Backfilling or rewriting already archived Changes, automatic conversion of old validation artifacts, or a receipt waiver for legacy mode.
- Changes to slice routing, task association, risk approval, continuation approval, spec promotion, archive commit behavior, or rollback semantics beyond the terminal receipt gate.

## Capabilities

- **Native final-gate evidence:** Run a non-empty, ordered declaration of final gates without a shell, bind the run to one canonical candidate identity, and retain immutable content-addressed exit and redacted output evidence with deterministic diagnostics for pass, failure, timeout, launch error, output overflow, or candidate mutation.
- **Sealed final-validation receipt:** Seal a completed native gate run to the exact root `validation.md`, preserving validator verdict facts and native all-gates-pass facts as separate fields; malformed, contradictory, stale, or tampered inputs cannot produce an archive-eligible receipt.
- **Fail-closed archive authorization:** For both legacy and fully completed sliced Changes, re-evaluate existing structural rules, semantic approval, receipt integrity, all gate facts, validation identity, and candidate identity immediately before any move; every failure leaves source, promoted specs, and archive destinations untouched.
- **Compatible validation-to-archive workflow:** Guide the validator through native gate run, semantic artifact write, and receipt seal, and guide the archiver to perform one native archive call and surface exact failures; active pre-receipt Changes remain routable but must refresh final validation and obtain a receipt before archive.

## Approach

Introduce one deep receipt module and expose a two-step native protocol through thin Typer adapters:

1. `change-gates-run` accepts only gate declarations: a unique stable gate ID, an argv array, a repository-relative working directory, and a bounded timeout. It does not accept candidate IDs, exit codes, output digests, verdicts, or pass/fail facts from the caller. It executes gates sequentially, exactly once, with stdin closed, no shell, a versioned inherited-environment policy, and deterministic record ordering. At least one gate is required; duplicate IDs, empty argv, absolute/traversing cwd values, symlink escapes, unsupported input versions, and secret values detected in argv are rejected before execution.
2. The validator uses the returned gate-run facts to finish root `validation.md`. The canonical `## Verdict` section must contain exactly one each of `verdict`, `critical`, and `gate-run`. `gate-run` names the content-addressed native run. Semantic approval means `verdict` is `pass` or `pass-with-warnings` and `critical` is decimal zero. `fail`, a positive count, disagreement between fields, duplicate or missing fields, an unknown verdict, or malformed structure is not approval. Product code validates this narrow envelope but never substitutes gate results for the validator's judgment.
3. `change-receipt-seal` takes only the Change name. It derives the referenced gate run from `validation.md`, verifies the run and current candidate, hashes the complete validation bytes, and atomically publishes a versioned receipt plus an atomic `current` pointer. It may preserve a non-approving or failed-gate receipt for diagnosis, but only a receipt with semantic approval and all native gates passing is archive-eligible. The validator must not edit `validation.md` after sealing.
4. `change-archive` keeps all current legacy/sliced structural, freshness, collision, and rollback checks. As its final preflight step, with no intervening external command or write, it strictly validates the current receipt and all referenced evidence, re-parses semantic facts, recomputes validation and candidate identities, and then performs the first move. Recheck never reruns gates, repairs data, selects an older receipt, or mutates a receipt.

The candidate policy is versioned and repository-wide. It canonically binds the Git `HEAD` identity (including an unborn state), index entries, tracked worktree bytes/types/modes/deletions, and every non-ignored untracked path. Separate canonical records preserve staged, unstaged, untracked, symlink, and submodule states. Paths and records are sorted by encoded repository-relative path and hashed with explicit labels and length delimiters. Unsupported path encodings, unreadable files, special files, escaping symlinks, Git inspection errors, or files changing during capture fail closed.

`.git/`, Git-ignored paths, root `validation.md` for the target Change, and that Change's receipt-owned evidence namespace are excluded from candidate identity. Root validation is excluded to avoid a gate-run/write cycle and is bound separately by its complete-byte SHA-256 digest. Receipt-owned paths are excluded to avoid self-reference. No other active Change, source, configuration, task, approval, slice-validation, or non-ignored untracked path is excluded. The gate runner captures the candidate before and after all gates; any difference makes the run non-passing and requires a fresh run. Ignored files and inherited environment may affect a local command, so a receipt proves recorded local execution facts, not hermetic reproducibility.

Each gate run and sealed receipt is canonical UTF-8 JSON with a schema name/version, deterministic key encoding, no wall-clock time or duration in the content-addressed core, and SHA-256 IDs over labeled length-delimited bytes. Gate records preserve declaration order and include argv, cwd, environment-policy ID, timeout policy, launch status, exit status, and stdout/stderr evidence path, byte count, and digest. Same inputs and retained evidence bytes produce the same IDs; nondeterministic command output legitimately produces a different run.

Evidence is append-only under the active Change and moves with it into the archive. Existing content-addressed objects are never overwritten; an exact existing object may be reused only after byte verification. A complete bundle is built in a sibling temporary location and atomically published, then `current` is atomically replaced. Interrupted or orphan temporary data is never eligible. All historical complete runs and receipts are retained in v1; there is no pruning command.

Only deterministically redacted stdout/stderr is persisted and hashed; raw output is held in memory only and discarded. The versioned redaction policy replaces exact non-empty values of secret-classified inherited environment variables and explicitly named secret environment variables before persistence. Secret values must be passed through the environment, never argv. Redaction markers, policy ID, and replacement counts are recorded, but secret values and raw-output digests are not. Each stream has a 1 MiB retained-byte limit; exceeding it terminates or fails that gate and cannot yield all-gates-pass. Binary bytes are supported without lossy text decoding. Missing evidence, a digest/length mismatch, an unknown redaction policy, or a non-regular/symlinked evidence file invalidates the run. Redaction reduces accidental retention but is not a general secret detector; validator instructions must avoid commands that print secrets.

Rollout is fail-closed at release: after this feature is enabled, every active legacy or sliced Change requires a receipt to archive, regardless of when it started. Existing artifacts remain readable and normal routing remains available, but an in-flight Change must rerun root final validation through the new run/write/seal protocol. Absence of a receipt routes or diagnoses the Change as needing final validation; direct archive also rejects it. Already archived Changes are untouched and no compatibility flag, timestamp cutoff, legacy exception, or manually authored receipt is accepted.

## Affected Areas

- `src/ai_harness/modules/harness/receipts.py` — new deep module owning schemas, canonical encoding, candidate capture, native execution, redaction, evidence storage, sealing, and strict verification.
- `src/ai_harness/modules/harness/change.py` — terminal routing and archive preflight integration while preserving mode-specific structural checks and all-or-nothing moves.
- `src/ai_harness/commands/change.py` and `src/ai_harness/main.py` — thin `change-gates-run` and `change-receipt-seal` adapters and registration; no policy duplication at the CLI edge.
- `src/ai_harness/resources/change-agent/change-validator.md` — declare/run gates natively, write the gate-run reference and semantic verdict, seal once, and report the receipt without post-seal edits.
- `src/ai_harness/resources/change-agent/change-archiver.md` — describe native final recheck and surface receipt/semantic failures without reinterpretation or retry.
- `tests/test_receipts.py` — canonicalization, candidate boundaries, execution outcomes, redaction/limits, immutable storage, sealing, tamper detection, and diagnostics.
- `tests/test_change.py`, `tests/test_change_sliced_archive.py`, and CLI tests — receipt-gated legacy/sliced lifecycle behavior, strict no-move failures, current-state recheck, and unchanged rollback/collision safeguards.
- `tests/test_renderers.py` and rendered fixtures — validator/archiver protocol and shared-envelope compatibility.

## Risks

- Repository-wide candidate identity can stale a receipt because of unrelated non-ignored work, including sibling Changes. This is deliberately conservative for v1; diagnostics must identify the changed state category/path without exposing file contents.
- Arbitrary argv can still invoke destructive programs. No-shell execution, closed stdin, cwd confinement, timeout, and output limits reduce ambiguity and resource abuse but do not provide sandboxing; only trusted configured gates may be declared.
- Output may contain secrets the deterministic policy does not recognize. Persist no raw output, redact known environment-derived values, reject known secret argv, bound evidence, document the residual risk, and never print retained output in routine archive errors.
- Content addressing detects accidental or partial tampering but, without a signing key or remote trust root, does not prove who invoked the native command. v1 claims deterministic integrity and current-state verification, not hostile-user attestation.
- A mutation after the immediate recheck and before/during filesystem moves remains possible under concurrent writers. Keep recheck adjacent to the first move, fail on observable capture races, and make no multi-process atomicity claim.
- Enforcing receipts can block in-flight Changes. Actionable diagnostics and a rerunnable final-validation protocol are the migration path; silent grandfathering would defeat the archive invariant.

## Rollback Plan

Revert the validator/archiver protocol, CLI registrations, receipt module, and archive gate together. Restore the previous validation-presence and sliced-freshness archive behavior without deleting receipt directories already written; they remain inert artifacts and move with any subsequently archived Change. Do not partially retain routing that requests receipts while archive ignores them, or archive enforcement without a native way to create them.

## Dependencies

- Target Python 3.12 or newer. Use the existing standard library, Typer CLI conventions, and repository module boundaries; add no runtime dependency. Questionary remains available for existing interactive flows, but receipt operations are non-interactive.
- Use `uv` for environment/command execution and repository workflows, `ruff` for format/lint gates, and `pytest` for tests. Follow TDD and existing atomic sibling-temp/replace and domain-error patterns.
- Keep receipt policy in `modules/harness/receipts.py`; CLI and prompt resources are adapters/consumers and must not reimplement hashing, parsing, redaction, or archive eligibility.
- Preserve shared result envelopes, existing task/approval schemas, and legacy/sliced archive rollback behavior. Tests must use controlled local subprocesses and temporary Git repositories, not network services.
- Per-task commits use `[add-verifiable-receipts][task_id] {slug}`.

## Success Criteria

- The same candidate, gate declarations, exit facts, redacted evidence, and validation bytes produce byte-identical canonical objects and IDs; record reordering, boundary ambiguity, unsupported schemas, or malformed JSON is rejected.
- Candidate identity changes for staged, unstaged, deleted, mode-changed, symlink, submodule, and non-ignored untracked changes, while ignored files, target root `validation.md`, and target receipt-owned writes follow their documented exclusions.
- A gate run cannot be marked passing when a command exits non-zero, fails to launch, times out, exceeds an output limit, lacks evidence, mutates the candidate, or has tampered evidence. Failed runs remain diagnosable without becoming archive-eligible.
- Persisted stdout/stderr is complete within limits, deterministically redacted, digest-verifiable, and free of known secret environment values; raw output is not written to disk.
- A validator-approved root validation and a current receipt whose native gates all passed allow archive for a structurally valid legacy Change and a fully completed sliced Change.
- Semantic approval with any failed native gate blocks archive, and all native gates passing with `verdict: fail`, `critical > 0`, or malformed/contradictory semantic facts also blocks archive.
- Missing/current-pointer errors, stale candidate or validation, unsupported schema/policy, duplicate gate IDs, changed command records, missing/tampered evidence, and manually malformed receipts all fail before specs promotion or change-folder movement.
- Archive performs the final verification after all earlier preflight checks and immediately before the first move; a recheck failure leaves source, specs destination, and archive destination unchanged.
- Active Changes without receipts receive actionable final-validation guidance and cannot use legacy mode or old artifact timestamps as a bypass; already archived Changes require no migration.
- Focused receipt, CLI, legacy archive, sliced archive, rollback, renderer, and end-to-end tests pass, followed by repository `uv`, `ruff`, and `pytest` gates.
