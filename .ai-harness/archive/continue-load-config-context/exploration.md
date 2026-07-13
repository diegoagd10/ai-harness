# Exploration — continue-load-config-context

## Budget
budget: 90

## Affected Files
- `src/ai_harness/modules/harness/change.py` — `change_continue()` derives the routed phase as `ChangeStatus.nextRecommended`; this is the domain seam that can instantiate `ChangeConfigAdministrator`, call `get_context_by(nextRecommended)` on every continuation, and carry the returned typed context in `ChangeStatus`.
- `src/ai_harness/commands/change.py` — the CLI already serializes nested dataclasses with `dataclasses.asdict`; its result type/documentation may need adjustment depending on whether the context reuses `phaseInstructions` or receives a dedicated status field.
- `tests/test_change.py` — add domain and CLI coverage for phase-to-config alias routing, ordered rule serialization, repeated reads after config edits, and failure behavior.
- `src/ai_harness/resources/change-agent/change-orchestrator.md` — document the context field in the `change-continue` JSON contract and instruct the orchestrator to forward it to the routed sub-agent.
- `expected/change-orchestrator.md` — keep the checked-in rendered expectation synchronized with the resource prompt.
- `.ai-harness/specs/agent-cli-contracts/orchestrator-cli-contract.md` — likely contract update if the established exhaustive `ChangeStatus` field list is maintained as active project documentation.

## Plan
- Derive status first in `change_continue()` and use its `nextRecommended` token (`explore`, `prd`, `design`, `specs`, `tasks`, `implement`, `validate`, or `archive`) as the argument to `ChangeConfigAdministrator.get_context_by`; the administrator already normalizes every routed token to the canonical `change_*` phase key.
- Attach the returned `ChangeConfigPromptContext` to the continuation response without caching, ensuring every invocation rereads `.ai-harness/config.yml` and observes user edits between phases.
- Choose and document the response-field contract. Reusing the existing, currently always-null `phaseInstructions` slot minimizes JSON schema growth but requires changing its misleading `str | None` type; a dedicated `configContext` field is clearer but expands the public `ChangeStatus` schema. In either case, preserve the context shape (`phase`, `phase_rules`) and let `asdict` plus `json.dumps` convert the rules tuple to a JSON array.
- Keep `change-new` behavior explicit: either leave its context field null until the first `change-continue`, or intentionally load explorer context there too; the concrete requirement only mandates loading on every `change-continue` invocation.
- Translate config-loading failures into the command's established `ChangeStoreError` path rather than leaking `FileNotFoundError` or YAML exceptions, after design confirms whether malformed-but-readable schemas must be rejected via `validate_config()` before `get_context_by()`.
- Update the orchestrator contract so it consumes the returned context for the sub-agent selected by `nextRecommended`, and synchronize the expected rendered prompt.

## Edge Cases
- `nextRecommended == "resolve-blockers"` has no configured phase alias; `get_context_by` deterministically returns that phase with empty rules, but design should confirm whether context should instead be null when no sub-agent is routable.
- Missing `.ai-harness/config.yml` currently makes `get_context_by()` raise raw `FileNotFoundError`; malformed YAML can raise `yaml.YAMLError`.
- `get_context_by()` is intentionally permissive and does not call `validate_config()`: wrong-shaped or non-list rules become empty rules, despite the module-level documentation saying integrity is validated before reading.
- Config edits between two calls must be visible; no administrator or context result should be cached across invocations.
- The routed `archive` token correctly normalizes to `change_archiver`; alternate task readiness paths do not alter that mapping.
- Tuple-valued `phase_rules` becomes a JSON array at the CLI boundary; tests should assert the public JSON shape rather than Python tuple identity.

## Test Surface
- Domain test: each representative `nextRecommended` value selects the matching canonical config phase, especially `prd -> change_propose` and `implement -> change_implementor`.
- CLI test: `ai-harness change-continue demo` emits the phase and ordered rules in its JSON response.
- Freshness test: edit `config.yml` after one continuation and verify the next invocation returns the new rules.
- Error tests: absent config, malformed YAML, and invalid schema follow the agreed CLI error contract with non-zero exit and no partial status JSON.
- Blocked-state test: verify the agreed empty/null context behavior for `resolve-blockers`.
- Regression gates: `pytest tests/test_change.py tests/test_change_config.py tests/test_renderers.py`, plus the repository lint/type-quality commands used by the implementation phase.

## Risks
- `ChangeStatus` is a documented public JSON contract. Renaming, repurposing, or adding a field can break prompt examples and external consumers; mitigate by selecting one stable field and updating all exhaustive contract lists.
- Loading config inside the generic `_derive_status()` would also affect `change-new`, archive preflight callers, and tests. Keep the integration at the `change_continue()` boundary unless broader behavior is deliberately approved.
- Calling `validate_config()` and then `get_context_by()` reads the file twice and has a race window. The requested public seam provides no validated-read operation, so design must choose between strict prevalidation and the exact single `get_context_by()` requirement without expanding the administrator's fixed three-method surface.
- The current status schema version is `1`; changing the JSON shape may warrant a version decision to avoid silent contract drift.

## Semantic Facts
- budget: 90
- follow_up: Design must settle the JSON field (`phaseInstructions` versus a dedicated context field), `change-new` behavior, schema-version handling, `resolve-blockers` behavior, and config validation/error translation before tasks are authored.
