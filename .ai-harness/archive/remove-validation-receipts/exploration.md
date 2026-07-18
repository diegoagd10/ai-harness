# Exploration — remove-validation-receipts

## Budget
650

## Affected Files

- **src/ai_harness/modules/harness/change.py** — Remove the receipt gate that currently forces every terminal archive route back to `validate` when no archive-eligible receipt is sealed. Concretely:
  - delete `_receipt_archive_eligible` (lines 89-102) and its only call site in `_derive_status`;
  - delete `_apply_receipt_route_override` (lines 334-358) and its single call site;
  - drop the receipt-authorization block at the bottom of `_finalize_route` (lines 857-865) so sliced terminal routes no longer bounce to `final-validate` when no receipt exists;
  - drop the receipt-error block in `_archive_preflight` (lines 1590-1596) and delete `_receipt_archive_error` (lines 1601-1629);
  - delete the `FinalValidationReceipts`/`ReceiptError` imports at the top of the file since they become unused.

- **src/ai_harness/commands/change.py** — Delete `change_gates_run_cmd` and `change_receipt_seal_cmd` (lines 71-156), their helpers, and the now-unused imports from `ai_harness.modules.harness.receipts`. These CLI commands exist solely to satisfy the gate being removed; without the gate they have no purpose and would just confuse users who expected archive to "just work" after validation.

- **src/ai_harness/main.py** — Drop the `change_gates_run_cmd`/`change_receipt_seal_cmd` imports (lines 9-11) and their `app.command(...)` registrations (lines 31-32).

- **tests/test_change.py** — Remove the receipt-creation steps from `test_change_continue_attaches_canonical_archiver_context_for_archive_route` (lines 421-473), `test_archive_requires_validation_and_non_empty_complete_tasks` (lines 600-676), and any test that asserts `nextRecommended == "validate"` purely because of a missing receipt. The expected routing becomes `nextRecommended == "archive"` as soon as `validation.md` declares a zero-critical verdict. The `_seal_receipt_for_archive` helper (lines 872-909) becomes unused.

- **tests/test_change_sliced_archive.py** — Remove the `_seal_archiveable_receipt` helper (lines 98-131) and its two call sites (lines 271 and 291). Sliced archive must succeed on a complete PRD + non-empty `validation.md` with a zero-critical verdict alone.

- **tests/test_receipts_archive.py** — The whole file (lines 1-403) exists to prove that `change_archive` denies without a receipt. Those scenarios are no longer the contract. Delete the file or rewrite it as a single negative test confirming the receipt's *absence* no longer blocks archive.

- **tests/test_receipts_routing.py** — `test_change_continue_routes_to_validate_when_no_receipt_for_legacy` (lines 134-148) must flip: without a receipt the legacy route must go to `archive` because validation already declares a pass verdict. `test_change_continue_routes_to_archive_when_receipt_present_for_legacy` (lines 142-147) becomes redundant — keep one test that proves routing on the verdict alone.

- **tests/test_receipts_cli.py** — Lines 1-293 only test `change-receipt-seal`/`change-gates-run`. With both commands gone, the entire file becomes dead and is deleted.

- **tests/test_receipts_seal.py** & **tests/test_receipts_verify.py** — These exercise `seal()` and `verify_for_archive()`. If the receipts module is *kept* (the validator prompt never references it, so the design choice is "remove the *requirement*" not "remove the receipts workflow"), `seal` and `verify_for_archive` lose their callers and become dead code; either delete the methods on `FinalValidationReceipts` or delete these tests. The codec, candidate-builder, executor, and envelope-parser tests stay.

- **src/ai_harness/resources/change-agent/change-validator.md** — Already documents the target behavior (lines 288-294: "pass or pass-with-warnings with critical: 0 → archive; fail or critical > 0 → route back to change-implementor"). No edits needed; this prompt is the authority the code currently diverges from.

- **src/ai_harness/resources/change-agent/change-orchestrator.md** — Spot-check that it does not tell the orchestrator to spawn `change-receipt-seal`; the existing grep is empty so no edits expected.

## Plan

1. **Drop the receipt gate from change.py routing.** Remove `_receipt_archive_eligible`, `_apply_receipt_route_override`, `_receipt_archive_error`, the receipt block in `_finalize_route`, and the receipt block in `_archive_preflight`. After this edit `_derive_status` returns `archive` whenever `artifacts["validate"] == "done"`, `progress.allComplete`, and the `validation.md` envelope parses with `verdict in {pass, pass-with-warnings}` and `critical == 0`. Failure of validation (`fail` or `critical > 0`) keeps routing to `validate`/`final-validate` via the unchanged upstream `next_recommended`/`_finalize_route` early-return branches.
2. **Add an envelope-aware archive condition.** The current `_archive_dependency` only checks `validate == done` and `progress.allComplete`. With the receipt gone, the FSM must read `validation.md` to confirm `verdict`/`critical` before recommending archive. Introduce a small helper `_validation_approved(change_dir)` that re-uses `parse_validation_envelope` and returns `True` only when the envelope is well-formed and `critical == 0` with `verdict in {"pass", "pass-with-warnings"}`. Wire it into `_archive_dependency` (legacy) and into the legacy terminal branch of `_finalize_route` so a missing/bad validation no longer routes straight to archive. This is the substitute for what the receipt's `archive_eligible` boolean used to gate.
3. **Delete the two receipt CLI commands.** Remove `change_gates_run_cmd` and `change_receipt_seal_cmd` from `commands/change.py`, prune imports, drop the registrations in `main.py`. Keep the rest of the CLI surface unchanged.
4. **Decide on the receipts module itself.** The codec, `parse_validation_envelope`, candidate builder, and gate-run executor can stay (the validator's archive routing will now call `parse_validation_envelope` directly through the new helper). `seal`/`verify_for_archive` lose every caller once the gate is gone — delete those methods, the receipt-bundle primitives they touch (`RECEIPT_SCHEMA_NAME`, the receipt-object kind, `_validate_receipt_schema`, `replace_current_pointer`), and the `RECEIPT_SCHEMA_NAME` test in `tests/test_receipts_codec.py` (line 110). Keep `RECEIPT_OBJECT_KIND_RUNS` and the executor because the validator does not depend on them but external callers might (call this out for design to confirm).
5. **Rewrite the affected tests.** For every test that called `_make_receipt`/`_seal_receipt_for_archive`/`_seal_archiveable_receipt`, drop the call and assert the archive path directly. Delete `test_receipts_archive.py`, `test_receipts_cli.py`, and the two routing tests in `test_receipts_routing.py` that assert the gate, replacing with one positive test that proves `nextRecommended == "archive"` from `validation.md` alone. Update `test_change.py::test_archive_requires_validation_and_non_empty_complete_tasks` to assert archive readiness from the envelope, not from a receipt.
6. **Add a regression test** in `test_change.py` covering the new rule: write `validation.md` with `verdict: pass-with-warnings` and `critical: 0` and confirm `change_continue` returns `nextRecommended == "archive"` without any receipt on disk. Mirror the test for sliced delivery using `validations/<cap>.md` plus the root `validation.md`.
7. **Run the gates.** `uv run ruff format --check .`, `uv run ruff check .`, `uv run pytest tests/`, then `./e2e/docker-test.sh`. Confirm no test still imports `FinalValidationReceipts` for `seal`/`verify_for_archive` purposes.

## Edge Cases

- **Validation file is missing** — the new `_validation_approved` returns `False`, so `_archive_dependency` stays `"blocked"` and `next_recommended` falls through to `validate`. Same surface as today for the no-validation case.
- **Validation is malformed** — `parse_validation_envelope` raises `ReceiptError`; the helper treats this as `False` and surfaces a routing diagnostic in `blocked_reasons` so users see *why* they were sent to validate.
- **Validation contradicts itself** — e.g. `verdict: pass` with `critical: 3`. The envelope parser already rejects this with `validation.contradictory`; the helper propagates that as `False` and the existing structural rules keep archive blocked.
- **Validation mtime older than latest continuation approval** (sliced mode) — already handled by the mtime check upstream of the receipt block in `_finalize_route`. That check stays.
- **Stale `.receipts/` directory left over from a previous workflow** — the receipts store uses paths under `.ai-harness/changes/<change>/.receipts/`; removing the requirement does not remove any on-disk state. Decide explicitly whether to leave it (no migration), wipe it on archive, or keep it untouched. **Recommendation:** leave it untouched so a future rollback restores full functionality; document the choice.
- **Validator writes `verdict: pass-with-warnings` and a non-zero critical count** — the parser already rejects this (line 3821 of receipts.py). Envelope parser remains authoritative.
- **The receipts module still re-exports `RECEIPT_SCHEMA_NAME` and `parse_validation_envelope`** — keep the latter (used by the new helper); drop the former.
- **CLI scripts in `expected/` snapshots** — verify the orchestrator/archiver prompts do not embed a literal `change-receipt-seal` invocation; grep showed none, so the snapshot stays stable.

## Test Surface

- **Existing tests to delete:** `tests/test_receipts_archive.py`, `tests/test_receipts_cli.py`, the two receipt-routing assertions in `tests/test_receipts_routing.py`, the receipt-prep branches in `tests/test_change.py` (3 sites) and `tests/test_change_sliced_archive.py` (2 sites).
- **Existing tests to keep but simplify:** `test_receipts_seal.py` and `test_receipts_verify.py` if the receipts module is partially kept; otherwise delete both. `test_receipts_codec.py`, `test_receipts_executor.py`, `test_receipts_candidate.py` stay — they exercise primitives the new helper depends on.
- **New tests to add:**
  - `tests/test_change.py::test_archive_route_from_pass_with_warnings_zero_critical` — `validation.md` declares `pass-with-warnings` and `critical: 0`; `change_continue` returns `archive` without any sealed receipt.
  - `tests/test_change.py::test_archive_route_blocks_on_fail_verdict` — `verdict: fail` with any critical count routes back to `validate`.
  - `tests/test_change.py::test_archive_route_blocks_on_missing_validation_md` — archive dependency stays `blocked`, `nextRecommended == "validate"`.
  - `tests/test_change.py::test_archive_route_blocks_on_malformed_validation_md` — surface a routing diagnostic, route to `validate`.
  - Sliced equivalents in `tests/test_change_sliced_archive.py` exercising the `final-validate` → `archive` transition with a zero-critical root validation and no receipt.
- **Gates:** `uv run ruff format --check .`, `uv run ruff check .`, `uv run pytest`, `./e2e/docker-test.sh` (per `change_validator.rules` in `.ai-harness/config.yml`).

## Risks

- **Risk: `pass-with-warnings` semantics drift.** Today the receipt's `archive_eligible` is `False` if native gates fail. With the receipt gone, archive only blocks on validation's `verdict`/`critical`. A user who relied on the receipt for an extra "all native gates passed" gate may be surprised. *Mitigation:* document the change in `change-validator.md` and the CHANGELOG; the validator already declares its policy as "CRITICAL only blocks".
- **Risk: archived Change leaves a `.receipts/` directory behind.** No data-loss risk but may confuse later audits. *Mitigation:* leave it untouched (no migration), and add a note to `change-archiver.md` documenting the state.
- **Risk: external scripts/CI invoke `ai-harness change-receipt-seal`.** Removing the CLI breaks those callers immediately. *Mitigation:* the change is explicitly "remove validation receipt requirements", so the CLI's removal is in scope; document in commit message and (if applicable) bump the agent-set metadata.
- **Risk: removing `seal`/`verify_for_archive` is too aggressive.** Some downstream tooling might still depend on them. *Mitigation:* design phase should confirm whether the receipts module is fully deleted or just bypassed. Exploration marks the question as `follow_up` so the design step resolves it before tasks land.
- **Risk: envelope parser exceptions bubble up into `_derive_status`.** Today `_derive_status` does not touch validation.md contents. Routing on the envelope makes it the first consumer of `parse_validation_envelope` inside `_derive_status`; a malformed file must surface as a routing diagnostic, not a `ChangeStoreError`. *Mitigation:* wrap the call in a try/except that converts any `ReceiptError` into `False` plus a `blocked_reasons` entry.
- **Risk: sliced mode regression.** `_finalize_route` is reached from sliced `archive_route_after_all_complete`; if the receipt block is removed but the mtime check stays, the slice path remains correct. *Mitigation:* confirm in tests that a sliced PRD with all continuations approved and a fresh `validation.md` with `critical: 0` archives without a receipt.
- **Risk: large test deletion churn.** Removing `test_receipts_archive.py` and `test_receipts_cli.py` will be visible in coverage reports. *Mitigation:* replace with the new routing tests above so coverage of archive readiness stays intact.
