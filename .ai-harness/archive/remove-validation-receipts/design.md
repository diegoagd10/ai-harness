# Design — remove-validation-receipts

## Context

`change_continue` refuses to route a fully-validated change to `archive` unless a
sealed `FinalValidationReceipt` exists on disk, forcing every change through the
`change-gates-run` / `change-receipt-seal` ritual. Yet `change-validator.md`
(lines 288-294) already declares the routing contract — `pass` or
`pass-with-warnings` with `critical: 0` → archive; `fail` or `critical > 0` →
route back — and the `## Verdict` envelope in `validation.md` already carries
every fact that contract needs. The receipt is a second, redundant source of
truth for archive readiness; the code has diverged from its own documented
contract. This change deletes the receipt gate and the receipt-only CLI, and
re-anchors archive routing on the validation envelope alone.

One load-bearing discovery shapes the whole design: the strict envelope parser
today requires exactly `{verdict, critical, gate-run}` in the `## Verdict`
section, but the validator's documented `validation.md` template
(`change-validator.md` lines 108-110) declares only `verdict:` and `critical:`.
With `change-gates-run` deleted, no new typed gate-run id can ever exist, so
keeping `gate-run` mandatory would make every future `validation.md`
"malformed" and block archive forever. The envelope grammar must therefore be
hard-trimmed to exactly `{verdict, critical}` — which is precisely the
documented contract. That trim in turn *forces* the deletion of `seal()` /
`verify_for_archive()`: both consume `ValidationEnvelope.gate_run`
(receipts.py lines 2759, 2779, 2791, 2807, 2832, 2870) and cannot survive the
field's removal. The two PRD scope items are coupled, not independent.

Module shape matters here because the temptation is to swap one gate for
another and leave the scaffolding standing. The deletion test must be applied
ruthlessly: every symbol whose only callers were the receipt gate or the
receipt CLI goes away; what remains is exactly what the two surviving public
seams reach.

## Deep modules

### Validation verdict gate (`src/ai_harness/modules/harness/change.py`)

- Seam: one private helper inside the change-status module, called from exactly
  three sites — the same sites where the receipt gate lived, so the public
  routing tokens (`nextRecommended`, `blockedReasons`) keep their shape.
- Interface:

  ```python
  def _validation_approved(change_dir: Path) -> tuple[bool, str | None]:
      """Return (archive-approved, diagnostic-when-not-approved).

      Reads ``change_dir / "validation.md"`` and parses it with
      ``parse_validation_envelope``. Approved iff the envelope is
      well-formed and ``envelope.approved`` (verdict in
      {pass, pass-with-warnings} and critical == 0).
      ``ReceiptError`` (missing *Verdict* section, duplicates,
      unknown keys, contradiction) and ``OSError`` (unreadable file)
      become ``(False, diagnostic)`` — never an exception; a missing
      file becomes ``(False, diagnostic)``. The diagnostic strings are
      routing-facing copy and are safe to surface verbatim in
      ``blockedReasons`` / preflight ``errors``.
      """
  ```

  Call sites:
  1. `_apply_validation_route_override(change_dir, fallback_route, slice_status)
     -> tuple[str, str | None]` — replaces `_apply_receipt_route_override` 1:1.
     When `fallback_route == "archive"` and the envelope is not approved,
     downgrades to `"validate"` (legacy) or `"final-validate"` (sliced) and
     returns the diagnostic; `_derive_status` appends a non-`None` diagnostic
     to `blockedReasons`. The `root`/`change`/`artifacts` parameters of the old
     override disappear — `fallback_route == "archive"` already implies
     `validate == done` structurally, and the envelope needs only `change_dir`.
  2. `_finalize_route(...)` (sliced terminal) — the receipt block at lines
     857-865 is replaced by an envelope check returning
     `("final-validate", diagnostic)` on disapproval, after the existing
     non-empty-file and mtime freshness checks (both unchanged). The
     `repository_root` parameter becomes unused and is dropped, along with the
     same now-unused parameter on `_archive_route_after_all_complete` and its
     call site (line 502).
  3. `_archive_preflight(...)` — **PRD gap this design closes**: the PRD lists
     the receipt block (lines 1590-1596) for removal but never substitutes the
     envelope check there. Without one, a direct `change_archive` call would
     archive a change whose `validation.md` declares `fail` — a routing bypass
     around the verdict. When `validation.md` exists, preflight runs
     `_validation_approved` and appends the diagnostic to `errors` on
     disapproval (missing-file case is already covered by the existing
     "Validation artifact missing" error).
- Hides: file reads, `ReceiptError`/`OSError` → diagnostic translation, the
  approved-verdict semantics, and the wording of routing diagnostics. Callers
  never touch the parser or exception types.
- Depth note: this helper replaces three receipt helpers
  (`_receipt_archive_eligible`, `_receipt_archive_error`,
  `_apply_receipt_route_override`) plus an entire pointer-verification stack
  with one pure predicate over the authoritative artifact. Deleting it would
  force three call sites to re-implement parsing and error translation — the
  deletion test passes decisively. `_archive_dependency` deliberately stays
  structural (`validate == done` + non-empty complete tasks) and does NOT read
  the envelope: putting the check there would flip `dependencies.archive` to
  `blocked`, make `_next_recommended` fall through to `"resolve-blockers"`,
  and silently change the public token contract from "route back to validate"
  to "unresolvable". The override shape preserves the documented tokens.

### Validation envelope parser (`src/ai_harness/modules/harness/receipts.py`)

- Seam: the existing public function — unchanged location, trimmed grammar.
- Interface:

  ```python
  def parse_validation_envelope(text: str | bytes) -> ValidationEnvelope: ...

  @dataclass(frozen=True, slots=True)
  class ValidationEnvelope:
      verdict: str    # "pass" | "pass-with-warnings" | "fail"
      critical: int   # non-negative, no leading zeros
      approved: bool  # verdict in {pass, pass-with-warnings} and critical == 0
  ```

  Grammar after trim: valid UTF-8 without BOM; exactly one unfenced level-2
  `## Verdict` section; inside it, blank lines plus exactly one each of
  `verdict:` and `critical:`; duplicates, unknown non-blank lines (including a
  legacy `gate-run:` line — strict decoders reject unknown keys), unknown
  verdicts, malformed counts, and contradictory `verdict`/`critical` pairs
  raise `ReceiptError`. The `gate_run` field, the `gate-run` expected key, and
  the `validate_typed_id` call in `_validate_verdict_fields` are deleted.
- Hides: section splitting across fenced code blocks, strict field grammar,
  contradiction rules, and the approved-boolean derivation.
- Depth note: this is THE semantic authority the PRD routes on — one strict
  parser, one definition of "zero-critical pass", consumed by the verdict gate
  above. Its grammar now matches `change-validator.md` verbatim, closing the
  code-vs-contract divergence the PRD names as intent. Deleting it would
  re-implement verdict parsing inside routing; it is deep by construction.

### Gate-run executor (`FinalValidationReceipts.run_gates`, receipts.py)

- Seam: unchanged public library method — kept per PRD scope, resolving the
  exploration `follow_up`: **`run_gates` and `RECEIPT_OBJECT_KIND_RUNS` stay.**
- Interface: `run_gates(*, change: str, request: GateRunRequest)
  -> GateRunResult`, plus its supporting public types and the codec
  (`decode_gate_declaration`, `encode_canonical`, `CodecError`, `typed_hash`,
  `validate_typed_id`, `build_candidate_identity`).
- Hides: candidate capture/stability, secret classification and argv
  rejection, subprocess confinement, evidence redaction, immutable bundle
  publication.
- Depth note: kept deliberately as a library seam even though its only CLI
  caller is deleted in this change — the PRD pins its survival, the executor
  tests (`tests/test_receipts_executor.py`) keep it honest, and recorded run
  bundles under `.receipts/runs/` remain meaningful history. It is NOT a
  bypass class: it has real, tested behavior and exactly one responsibility.
  Everything NOT reachable from this seam or from
  `parse_validation_envelope` is deleted — that is the trim rule:

  - methods: `seal`, `verify_for_archive`;
  - types: `SealResult`, `ArchiveAuthorization`;
  - helpers consumed only by those methods: `_load_run`,
    `hash_validation_bytes`, `_validate_receipt_schema`;
  - pointer machinery consumed only by seal/verify:
    `ReceiptObjectStore.replace_current_pointer`, `read_current_pointer`,
    `RECEIPT_POINTER_FILENAME`, `RECEIPT_POINTER_SCHEMA_NAME`,
    `RECEIPT_POINTER_SCHEMA_VERSION`, `RECEIPT_POINTER_LABEL`;
  - receipt-object kind and schema: `RECEIPT_OBJECT_KIND_RECEIPTS`,
    `RECEIPT_ID_LABEL`, `VALIDATION_ID_LABEL`, `RECEIPT_SCHEMA_NAME`,
    `RECEIPT_SCHEMA_VERSION`, `CANONICAL_KEYS["receipt"]` — the store's kind
    dispatch collapses to the single `runs` kind (`_id_label_for_kind`
    simplifies accordingly; `RECEIPT_OBJECT_FILENAME` stays, shared by runs);
  - `__all__` is pruned to match; ruff is the no-dangling-imports gate.

### Change CLI adapter (`src/ai_harness/commands/change.py`, `src/ai_harness/main.py`)

- Seam: the typer command surface — subtractive only.
- Interface after: `change-new`, `change-continue`, `change-approve`,
  `change-archive`, `task-create`, `task-list`, `task-next`, `task-done`.
  Deleted: `change_gates_run_cmd`, `change_receipt_seal_cmd`, and their
  exclusive helpers (`_seal_summary`, `_parse_gate_run_request`); imports of
  `CodecError`, `FinalValidationReceipts`, `GateRunRequest`, `ReceiptError`,
  `SealResult`, `decode_gate_declaration` are pruned to whatever the surviving
  commands still use; the two imports and two `app.command(...)` registrations
  in `main.py` (lines 9-11, 31-32) are dropped. Invoking either deleted
  command now errors as an unknown command — the intended breaking behavior.
- Hides: nothing new — this module remains a thin JSON adapter over
  `modules/harness/change.py`.
- Depth note: shallow by design (adapter boundary); its depth lives behind
  the module seams it calls.

## Internal collaborators

Not public test seams — covered transitively through the seams above, never
mocked:

- `ReceiptObjectStore` (runs-kind only after the trim) — immutable bundle
  publication/reads for the executor; exercised through
  `tests/test_receipts_executor.py` and `tests/test_checkpoint_bundle_store.py`.
- `_ImmutableBundleStore` — shared hardened bundle mechanics; the checkpoint
  store composes it (composition over inheritance, per project rule) and its
  tests stay untouched except the kind-closure test noted below.
- Candidate builder internals (`_capture_candidate`, git-worktree policy),
  secret classification/redaction helpers, `_resolve_git_top_level`,
  `_stable_regular_read` — kept only where reachable from `run_gates`.
- `_split_verdict_sections`, `_parse_verdict_lines`, `_validate_verdict_fields`,
  `_envelope_from_fields` — parser internals, covered by the re-homed parser
  tests.

Test-surface consequences the PRD missed, fixed here:

- `tests/test_checkpoint_bundle_store.py::test_public_receipt_object_store_remains_closed_to_checkpoint_kinds`
  imports `RECEIPT_OBJECT_KIND_RECEIPTS` (lines 405-410) — rewrite to assert
  the public kind set is exactly `{RECEIPT_OBJECT_KIND_RUNS}`.
- Envelope fixtures in `tests/test_change.py` (lines 465, 669, 905),
  `tests/test_change_sliced_archive.py` (line 128), and
  `tests/test_receipts_routing.py` (lines 90, 128) embed `gate-run:` lines that
  the trimmed parser will reject — drop the field when the receipt-prep helpers
  (`_make_receipt`, `_seal_receipt_for_archive`, `_seal_archiveable_receipt`)
  are removed.
- Envelope-parser unit tests currently living inside
  `tests/test_receipts_seal.py` (lines 82-154) survive the file's deletion by
  re-homing to `tests/test_validation_envelope.py`, rewritten to the two-field
  grammar plus one new case asserting a `gate-run:` key is rejected as unknown.

## Seam map

```
change-continue / change-archive  (typer, commands/change.py + main.py)
        |
        v
modules/harness/change.py  (file-backed FSM; status derived from disk)
   _derive_status
     |-- legacy: _next_recommended(artifacts, dependencies)
     |            -> _apply_validation_route_override  ---+
     |-- sliced: _archive_route_after_all_complete       |
     |            -> _finalize_route  -------------------+--> _validation_approved
   _archive_preflight  ----------------------------------+        |
                                                                   v
                                          receipts.parse_validation_envelope
                                          (text -> ValidationEnvelope; ReceiptError)
                                          [strict 2-field grammar: verdict, critical]

receipts.FinalValidationReceipts.run_gates   (library seam; no CLI caller after trim)
        -> ReceiptObjectStore (runs kind only)
        -> candidate builder / codec / evidence-redaction internals
```

Cross-module seams after the change: exactly two — `parse_validation_envelope`
(change.py → receipts.py) and `run_gates` (external/library → receipts.py). The
receipt pointer, receipt schema, and sealing seams are gone, not moved.

## Rejected alternatives

For the load-bearing seam — *what parses the verdict and what grammar it
accepts* — designed three ways:

1. **Keep the 3-field envelope, add `gate-run:` to `change-validator.md`.**
   Rejected. The PRD forbids editing the validator resource, and with
   `change-gates-run` deleted the field would reference runs nothing can
   create — a permanently dead concept inscribed in the contract. It also
   leaves `seal` technically alive, inviting the "bypass rather than delete"
   outcome the project rules prohibit.
2. **Optional `gate-run` field.** Rejected. Optional keys contradict the
   module's strict-decoder philosophy ("strict decoders reject unknown keys —
   nothing may be added without bumping the schema version") and keep a
   vestigial concept in the grammar forever. Hard-trimming to exactly
   `{verdict, critical}` makes the grammar IS the contract, matching the
   documented validator template verbatim. Accepted cost: in-flight changes
   whose `validation.md` carries a legacy `gate-run:` line must re-run the
   validator (it rewrites the file); noted for the commit message.
3. **Separate lenient routing parser for `verdict`/`critical`.** Rejected.
   Two parsers for one `## Verdict` section is the classic shallow-seam
   smell: it duplicates logic, guarantees drift, and leaves the strict parser
   with no production caller. One trimmed parser is deeper than two
   overlapping ones.

For the wiring shape:

4. **Envelope check inside `_archive_dependency` instead of a route
   override.** Rejected. It flips `dependencies.archive` to `blocked`, so
   `_next_recommended` returns `"resolve-blockers"` instead of routing back to
   `validate`/`final-validate` — a silent change to the public token contract
   and to downstream consumers of `nextRecommended`. The override shape
   preserves the documented routing exactly where the receipt gate sat.
5. **Delete the entire receipts module.** Rejected per PRD out-of-scope: the
   envelope parser is the routing authority this design depends on, and the
   executor/codec/candidate builder are pinned survivors. The trim rule
   (delete only what neither surviving seam reaches) is the deletion test
   applied mechanically.
6. **Leave `seal`/`verify_for_archive` as dead code for one slice.** Rejected.
   Dead public seams are bypass classes in waiting, and the grammar trim makes
   them un-compilable anyway (they consume `ValidationEnvelope.gate_run`).
   Rollback is a git revert, not retained code — on-disk `.receipts/`
   directories stay untouched precisely so a revert restores the full previous
   workflow (a one-line note to `change-archiver.md` documents that state).
