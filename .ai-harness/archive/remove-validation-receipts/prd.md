# PRD — remove-validation-receipts

## Intent

Today, `change_continue` refuses to route to `archive` after validation passes unless a
sealed `FinalValidationReceipt` exists on disk. This forces every change through a
receipt-sealing ritual (`change-gates-run` / `change-receipt-seal`) even though the
validation envelope in `validation.md` already carries the full verdict (`pass`,
`pass-with-warnings`, `fail`, `critical` count) needed to decide archive readiness.
The documented contract in `change-validator.md` is already "pass or pass-with-warnings
with critical: 0 → archive; fail or critical > 0 → route back"; the code diverges from
it. Remove the receipt requirement so archive is gated purely on the validation
envelope, and delete the receipt-only CLI surface that exists solely to satisfy the gate.

## Scope

### In

- Remove the receipt gate from `src/ai_harness/modules/harness/change.py` routing:
  `_receipt_archive_eligible`, `_apply_receipt_route_override`, `_receipt_archive_error`,
  the receipt-authorization block in `_finalize_route`, the receipt block in
  `_archive_preflight`, and the now-unused `FinalValidationReceipts`/`ReceiptError`
  imports.
- Add an envelope-aware archive condition: a helper (e.g. `_validation_approved`) that
  parses `validation.md` via `parse_validation_envelope` and returns `True` only when
  the envelope is well-formed, `verdict ∈ {pass, pass-with-warnings}`, and
  `critical == 0`. Wire it into the legacy archive dependency and the legacy terminal
  branch of `_finalize_route`. Malformed/missing envelopes must surface as routing
  diagnostics (blocked reasons), not raise `ChangeStoreError`.
- Delete the receipt-only CLI: `change_gates_run_cmd` and `change_receipt_seal_cmd`
  from `src/ai_harness/commands/change.py`, their imports and `app.command(...)`
  registrations in `src/ai_harness/main.py`.
- Trim the receipts module: remove `seal()` / `verify_for_archive()` and the
  receipt-bundle primitives that only they consume (`RECEIPT_SCHEMA_NAME`, the
  receipt-object kind, `_validate_receipt_schema`, `replace_current_pointer`) once their
  last callers are gone. Keep `parse_validation_envelope`, the codec, candidate builder,
  and gate-run executor — the new routing helper depends on the parser, and the
  executor/codec tests stay.
- Rewrite/delete affected tests: drop receipt-sealing helpers
  (`_make_receipt`, `_seal_receipt_for_archive`, `_seal_archiveable_receipt`) and their
  call sites; delete `tests/test_receipts_archive.py` and `tests/test_receipts_cli.py`;
  replace receipt-gating routing tests in `tests/test_receipts_routing.py` with
  verdict-driven assertions; delete or rewrite `tests/test_receipts_seal.py` and
  `tests/test_receipts_verify.py` to match the trimmed module surface; drop the
  `RECEIPT_SCHEMA_NAME` case in `tests/test_receipts_codec.py`.
- Add regression tests proving archive routing from the envelope alone (legacy and
  sliced paths), and negative tests for `fail` verdict, missing `validation.md`, and
  malformed `validation.md`.
- Target Python >=3.12; run with `uv`; style via `ruff format --check .` and
  `ruff check .`; tests via `uv run pytest tests/`; e2e via `./e2e/docker-test.sh`.

### Out

- No deletion of the receipts module as a whole: the envelope parser, codec, candidate
  builder, and gate-run executor remain (design phase confirms final trim extent).
- No changes to `change-validator.md` — it already documents the target routing.
  `change-orchestrator.md` spot-check only (grep shows no `change-receipt-seal`
  references).
- No migration or cleanup of on-disk `.receipts/` directories from prior workflows;
  they are left untouched so rollback restores full functionality.
- No change to the mtime-based freshness checks in `_finalize_route` (sliced mode).
- No GitHub publish; no parent/child decomposition (this is a single-budget change).

## Capabilities

- Envelope-driven archive routing (legacy): `change_continue` returns
  `nextRecommended == "archive"` when `validation.md` declares `pass` or
  `pass-with-warnings` with `critical: 0`, all tasks complete, and no receipt exists
  on disk — specifiable and testable end-to-end in `tests/test_change.py`.
- Envelope-driven archive routing (sliced): the `final-validate` → `archive` terminal
  transition in `_finalize_route` succeeds on a fresh, zero-critical root
  `validation.md` (plus per-capability `validations/<cap>.md`) without a receipt —
  specifiable in `tests/test_change_sliced_archive.py`.
- Validation-blocked routing preserved: `fail` verdict, `critical > 0`, missing
  `validation.md`, or malformed/contradictory envelope keeps archive `blocked` and
  routes back to `validate`/`final-validate` with a diagnostic in `blocked_reasons`.
- Receipt CLI removal: `change-gates-run` and `change-receipt-seal` no longer appear in
  the CLI surface or registrations; invoking them errors as unknown commands.
- Receipt module trim: `seal`/`verify_for_archive` and receipt-bundle primitives are
  removed from `ai_harness.modules.harness.receipts` with no dangling imports; envelope
  parser, codec, candidate builder, and executor keep passing their existing tests.

## Approach

1. **Drop the gate first.** Delete the five receipt-touching sites in
   `modules/harness/change.py` (helpers, call sites, `_finalize_route` block,
   `_archive_preflight` block, imports). After this edit, `_derive_status` routes to
   `archive` whenever the structural conditions hold — but archive readiness must not
   regress on missing/bad validation, so…
2. **Substitute envelope gating.** Introduce `_validation_approved(change_dir)` that
   calls `parse_validation_envelope` inside try/except, converting `ReceiptError` into
   `False` plus a `blocked_reasons` diagnostic. Wire it into `_archive_dependency` and
   the legacy terminal branch of `_finalize_route`. The upstream
   `next_recommended`/`_finalize_route` early-return branches for failed validation
   stay unchanged.
3. **Remove the CLI.** Delete both command functions and their helpers from
   `commands/change.py`, prune imports, drop the two `app.command(...)` registrations
   in `main.py`.
4. **Trim the receipts module.** Once the gate and CLI are gone, `seal` and
   `verify_for_archive` have no callers; remove them and their exclusive primitives.
   Design confirms whether `RECEIPT_OBJECT_KIND_RUNS`/executor stay (exploration marks
   this `follow_up`; keep unless design says otherwise).
5. **Rewrite tests.** Delete the two fully-receipt test files and the receipt-prep
   branches in change/archive tests; add the new envelope-routing regression tests
   listed in exploration; mirror for sliced delivery.
6. **Run gates.** `uv run ruff format --check .`, `uv run ruff check .`,
   `uv run pytest tests/`, then `./e2e/docker-test.sh`. Grep to confirm no remaining
   import of `FinalValidationReceipts` for `seal`/`verify_for_archive`.

## Affected Areas

- `src/ai_harness/modules/harness/change.py` — routing/status derivation, archive
  preflight, route finalization; new `_validation_approved` helper.
- `src/ai_harness/modules/harness/receipts.py` — remove `seal`,
  `verify_for_archive`, `RECEIPT_SCHEMA_NAME`, receipt-object kind,
  `_validate_receipt_schema`, `replace_current_pointer`.
- `src/ai_harness/commands/change.py` — delete `change_gates_run_cmd`,
  `change_receipt_seal_cmd`, helpers, imports.
- `src/ai_harness/main.py` — drop imports and command registrations.
- `tests/test_change.py` — remove receipt prep (3 sites), update
  `test_archive_requires_validation_and_non_empty_complete_tasks`, add envelope-routing
  regressions.
- `tests/test_change_sliced_archive.py` — remove `_seal_archiveable_receipt` and call
  sites; add sliced `final-validate → archive` regression.
- `tests/test_receipts_archive.py` — delete (or collapse to one negative test).
- `tests/test_receipts_cli.py` — delete.
- `tests/test_receipts_routing.py` — flip/remove the two receipt-gating routing tests;
  keep one verdict-driven test.
- `tests/test_receipts_seal.py`, `tests/test_receipts_verify.py` — delete or rewrite to
  match trimmed module surface.
- `tests/test_receipts_codec.py` — drop `RECEIPT_SCHEMA_NAME` case (line ~110).

## Risks

- **`pass-with-warnings` semantics drift.** The receipt's `archive_eligible` also
  encoded native-gate success; without it, archive blocks only on verdict/critical.
  *Mitigation:* the validator's documented policy is already "CRITICAL only blocks";
  note the behavior change in the commit message.
- **External scripts/CI invoking `change-receipt-seal` break immediately.**
  *Mitigation:* removal is the explicit goal; call it out in the commit message
  (`[remove-validation-receipts][...] ...` per commit format) and consider bumping
  agent-set metadata.
- **Envelope parser exceptions leaking into `_derive_status`.** Routing becomes the
  first consumer of `parse_validation_envelope` in status derivation.
  *Mitigation:* wrap in try/except; `ReceiptError` → `False` + `blocked_reasons`
  diagnostic, never a `ChangeStoreError`.
- **Removing `seal`/`verify_for_archive` may be too aggressive** if downstream tooling
  depends on them. *Mitigation:* design phase confirms trim extent (exploration flags
  as `follow_up`); if in doubt, bypass rather than delete in the first slice.
- **Sliced-mode regression.** `_finalize_route` is reached from
  `archive_route_after_all_complete`; the mtime freshness check must stay.
  *Mitigation:* sliced regression test with fresh zero-critical root validation.
- **Coverage churn from deleting `test_receipts_archive.py` / `test_receipts_cli.py`.**
  *Mitigation:* new envelope-routing tests replace the archive-readiness coverage.
- **Stale `.receipts/` dirs confuse audits.** *Mitigation:* leave untouched; add a note
  to `change-archiver.md` documenting the state.

## Rollback Plan

Purely subtractive code change with no data migration: revert the commits to restore
the receipt gate, CLI commands, and module methods exactly as before. Because no
on-disk `.receipts/` state is modified or deleted, a rollback re-enables the full
previous workflow for any change that had receipts sealed. No forward/backward
compatibility shim is needed — old `validation.md` envelopes remain valid inputs to
the restored parser.

## Dependencies

- Existing `parse_validation_envelope` in
  `src/ai_harness/modules/harness/receipts.py` — the source of truth for verdict and
  critical count; must remain intact and exported.
- `change-validator.md` resource — already the routing authority; no edit required but
  behavior must match its documented contract.
- Toolchain per config: Python >=3.12, `uv`, `ruff`, `pytest`, `typer`, `questionary`.
- No parent change (not a budget-decomposed child); no external service dependencies.

## Success Criteria

1. `change_continue` returns `nextRecommended == "archive"` for a change with
   `validation.md` declaring `pass` or `pass-with-warnings` and `critical: 0`, all
   tasks complete, and **no receipt on disk** — verified by new regression tests in
   `tests/test_change.py`.
2. Sliced delivery: `final-validate` → `archive` succeeds on a fresh, zero-critical
   root `validation.md` with no receipt — verified in
   `tests/test_change_sliced_archive.py`.
3. `fail` verdict, `critical > 0`, missing `validation.md`, and malformed/contradictory
   envelope each keep archive blocked and route to `validate`/`final-validate` with a
   `blocked_reasons` diagnostic — verified by negative tests.
4. `change-gates-run` and `change-receipt-seal` are absent from the CLI; `seal` /
   `verify_for_archive` and receipt-bundle primitives are absent from the receipts
   module with no dangling imports (ruff clean).
5. `uv run ruff format --check .`, `uv run ruff check .`, `uv run pytest tests/`, and
   `./e2e/docker-test.sh` all pass.
