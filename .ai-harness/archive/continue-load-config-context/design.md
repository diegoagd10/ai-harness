# Design — continue-load-config-context

## Context

`change-continue` already derives the next lifecycle route from file-backed artifacts, while `ChangeConfigAdministrator` already owns repository configuration validation, phase aliases, YAML reading, and typed prompt context. The change must join those existing seams without putting configuration I/O into the reusable status derivation path: every continuation derives status first, skips configuration for `resolve-blockers`, and otherwise validates and reads the routed phase through the administrator. The public `ChangeStatus` contract advances uniformly to schema version 2, adds nullable `configContext`, and preserves all version-1 fields and meanings. A successful continuation is therefore a self-contained routing message; a configuration failure produces no partial status output.

## Deep modules

### Change continuation
- Seam: `change_continue(root: Path, change: str) -> ChangeStatus` in `src/ai_harness/modules/harness/change.py`.
- Interface: Keep the existing function signature and `ChangeStoreError` failure type. After existence checking, call the side-effect-free `_derive_status`, inspect `status.nextRecommended`, and return a new immutable status with `configContext=None` for `resolve-blockers`. For each actionable token (`explore`, `prd`, `design`, `specs`, `tasks`, `implement`, `validate`, `archive`), construct `ChangeConfigAdministrator(repo_root=root)`, require `validate_config().is_valid`, then call `get_context_by(status.nextRecommended)` and attach the returned `ChangeConfigPromptContext`. Validation warnings do not halt delivery. Translate administrator validation/read/parse failures and an invalid verdict into `ChangeStoreError` with useful configuration-specific text. Never return the already-derived status after configuration failure.
- Hides: The sequencing invariant (derive → classify route → validate → required read → immutable replacement), blocker bypass, exception normalization, and per-invocation administrator lifecycle. It deliberately delegates alias mapping; there is no duplicate route-to-config table in the harness module. The required validation/read pair may read twice and has a narrow edit race; a failure from either operation is normalized, and no cache or direct YAML fallback is introduced.
- Depth note: This seam concentrates lifecycle orchestration and failure atomicity behind the operation callers already use; deleting it would force the CLI and other callers to reproduce routing and configuration policy.

### Change configuration administrator
- Seam: Existing `ChangeConfigAdministrator(repo_root)` methods `validate_config()` and `get_context_by(change_phase)` in `src/ai_harness/modules/change_config/module.py`; its public three-method surface remains unchanged.
- Interface: `validate_config() -> ChangeConfigValidationResults` establishes that configuration is deliverable; `is_valid=False` is halting while `warnings` are informational. `get_context_by(nextRecommended) -> ChangeConfigPromptContext` is called exactly once after successful validation for every actionable continuation and remains the sole owner of alias normalization, including `prd → change_propose`, `implement → change_implementor`, and `archive → change_archiver`. It returns canonical `phase` and ordered `phase_rules`. It is never called for `resolve-blockers`.
- Hides: Config path construction, YAML parsing, schema inspection, canonical phase aliases, source ordering, and conversion to immutable tuples. A fresh administrator/read path on every `change_continue` invocation makes edits visible; no object or result survives an invocation.
- Depth note: A small validate/read interface hides both persistence and phase vocabulary; duplicating YAML access or aliases in continuation would make both modules shallow and inconsistent.

### Change status contract
- Seam: `ChangeStatus` in `src/ai_harness/modules/harness/change.py`, serialized recursively by the existing `dataclasses.asdict` CLI edge.
- Interface: Add a final field `configContext: ChangeConfigPromptContext | None`; set `_SCHEMA_VERSION = 2` for every status producer. `change_new` continues to call only `_derive_status`, performs no config access, and returns version 2 with `configContext=None`. `_derive_status` supplies the null default so it remains a pure file-backed state derivation. `change_continue` replaces only `configContext` after successful loading. Existing fields, including `phaseInstructions: str | None`, retain names, order, and meaning. JSON serialization emits `configContext` as either `null` or `{ "phase": <canonical key>, "phase_rules": [<rules in source order>] }`; recursive `asdict` converts the internal tuple to an array without a custom encoder.
- Hides: Python immutability and tuple representation, uniform schema-version construction, and the distinction between raw derived state and continuation-enriched state. The CLI remains unaware of phase aliases and configuration models.
- Depth note: One typed response boundary carries the full orchestration contract; a parallel response DTO or manual dictionary assembler would duplicate the schema and serialization rules.

### Orchestrator response contract
- Seam: `src/ai_harness/resources/change-agent/change-orchestrator.md`, its checked-in `expected/change-orchestrator.md`, and `.ai-harness/specs/agent-cli-contracts/orchestrator-cli-contract.md`.
- Interface: Document the complete version-2 status shape for both commands: `change-new` has null context; successful routed `change-continue` has the exact `configContext` object. Require the orchestrator to forward that object unchanged to the sub-agent selected by `nextRecommended`, and to forward nothing when the route is `resolve-blockers`. Keep the PRD's representative `prd` response coherent with canonical `change_propose` and ordered rules.
- Hides: Prompt rendering and synchronization of executable behavior with agent-facing command authority.
- Depth note: This is the external consumer seam: one contract prevents the orchestrator from independently reading config or reconstructing aliases.

## Internal collaborators

- `_derive_status(root, change) -> ChangeStatus` remains an internal, transitively tested collaborator. It derives artifact state and returns the version-2 base object with null context; it must not instantiate the administrator, validate config, or distinguish `change-new` from `change-continue`.
- An internal continuation enrichment helper is optional only if it keeps `change_continue` readable. Its input should be `(root, derived_status)` and its output a replaced `ChangeStatus`; it is not exported, injected, or mocked. A helper that merely renames `validate_config`/`get_context_by` calls is too shallow and should be folded into `change_continue`.
- `ChangeConfigPromptContext` remains the administrator's immutable value object and is embedded directly in `ChangeStatus`; no adapter model is added.
- `src/ai_harness/commands/change.py` remains a thin adapter. `_print_json`/`_to_jsonable` continue using `asdict`; `change_continue_cmd` continues catching only the domain-level `ChangeStoreError`, writing its message to stderr, exiting non-zero, and emitting no stdout. Configuration exceptions must therefore be normalized before crossing the harness seam.
- Tests use real temporary repositories and real config files at the public seams. `tests/test_change_config.py` owns administrator alias/validation behavior. `tests/test_change.py` owns continuation integration, all eight routed values, blocker bypass, freshness after file edits, schema-v2/new compatibility, ordered JSON serialization, and missing/malformed/invalid config failures with empty stdout. Renderer tests own source/expected prompt parity and documented forwarding. Private helpers and YAML internals are covered transitively and are not mock seams; a narrow spy may verify that `resolve-blockers` does not call `get_context_by`, but phase outcomes should be asserted through returned values.

## Seam map

1. CLI `change_continue_cmd` → `change_continue(root, change)`; it knows only `ChangeStatus` and `ChangeStoreError`.
2. `change_continue` → pure `_derive_status` → actionable route or `resolve-blockers`.
3. Actionable route: `change_continue` → fresh `ChangeConfigAdministrator(root).validate_config()` → `get_context_by(nextRecommended)` → immutable `ChangeStatus.configContext`.
4. Blocked route: `change_continue` → `configContext=None`, with no administrator read.
5. `ChangeStatus` → existing recursive `asdict` serialization → version-2 JSON → orchestrator forwards `configContext` to the selected sub-agent.
6. `change_new` → `_derive_status` only → version-2 JSON with null context; it does not depend on repository config availability.

## Rejected alternatives

- Put configuration loading in `_derive_status`. Rejected because it couples reusable file-backed derivation to config I/O, makes `change-new` fail or load context, and affects archive/internal callers. The continuation boundary is the higher, behavior-specific seam.
- Add a route-to-canonical-phase map in the harness. Rejected as a shallow alias adapter that duplicates the administrator's vocabulary and can drift; pass `nextRecommended` directly to `get_context_by`.
- Repurpose `phaseInstructions`. Rejected because it is a nullable string with an established meaning, whereas configuration context is structured data. A dedicated nullable field is clearer and preserves compatibility.
- Return a continuation-only response subtype or manually build JSON in the CLI. Rejected because two status schemas would force consumers and tests to duplicate most fields. A uniformly versioned additive field keeps one deep response seam.
- Validate only, or read YAML directly after validation. Rejected because a successful actionable invocation must reach `get_context_by`; direct access leaks parsing and alias complexity. Conversely, calling only permissive `get_context_by` would allow schema-invalid configuration through.
- Extend the administrator with a combined validated-read method. It would remove the double-read race, but violates the fixed three-method seam and is unnecessary for this change. The design accepts the documented narrow race and normalizes failures from either read.
- Cache the administrator, parsed config, or context. Rejected because user edits between invocations are part of the lifecycle contract and must be observable immediately.
- Treat `resolve-blockers` as a config phase with empty rules. Rejected because it is a synthetic non-routable status, not a sub-agent phase; null explicitly prevents accidental dispatch.
- Keep schema version 1 because the field is additive. Rejected because exhaustive consumers need an explicit compatibility signal. All `ChangeStatus` producers move together to version 2 while retaining the complete version-1 field set.
