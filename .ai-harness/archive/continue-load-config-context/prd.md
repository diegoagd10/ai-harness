# PRD — continue-load-config-context

## Intent

Make every successful `ai-harness change-continue {change}` response self-contained for orchestration: the command derives the next routed phase, loads that phase's current repository configuration through `ChangeConfigAdministrator.get_context_by`, and returns the context in JSON so the orchestrator can pass it to the selected sub-agent.

## Scope

### In

- Load phase-specific context on every `change-continue` invocation, after deriving `nextRecommended` and without caching across invocations.
- Route all actionable lifecycle phases through the aliases already owned by `ChangeConfigAdministrator`: `explore`, `prd`, `design`, `specs`, `tasks`, `implement`, `validate`, and `archive`.
- Add a dedicated `configContext` field to `ChangeStatus` JSON. For a routed phase it is an object with `phase` (the canonical `change_*` key) and `phase_rules` (an ordered JSON array of configured rules).
- Return `configContext: null` when `nextRecommended` is `resolve-blockers`, because no sub-agent is routable in that state; do not call `get_context_by` with the synthetic blocker token.
- Validate configuration before context delivery. Missing files, malformed YAML, or schema-invalid configuration are command failures translated to the existing `ChangeStoreError`/CLI error path.
- Update the orchestrator's documented CLI contract and instructions so it forwards `configContext` to the sub-agent selected by `nextRecommended`.
- Preserve context freshness, rule order, and exact configured rule text.

### Out

- Loading context in `change-new`; its `configContext` remains `null`.
- Changing phase progression, artifact gates, task readiness, or archive behavior.
- Changing config schema, phase aliases, default rules, or configuration mutation commands.
- Adding context to task commands or invoking sub-agents from the CLI itself.
- Caching configuration or context between command invocations.

## Capabilities

- Routed context delivery: A successful `change-continue` response contains the current configuration context for the phase named by `nextRecommended`.
- Complete lifecycle routing: Each actionable continuation phase resolves to its canonical configured phase, including non-obvious aliases such as `prd` → `change_propose`, `implement` → `change_implementor`, and `archive` → `change_archiver`.
- Safe blocked-state response: A continuation with no routable phase reports `resolve-blockers` and a null context rather than inventing a configuration phase.
- Deterministic configuration failure: Invalid or unavailable configuration stops continuation with the established non-zero CLI error behavior and emits no partial status JSON.
- Orchestrator context forwarding: The orchestrator consumes the response context and supplies it to the routed sub-agent without independently reading configuration.

## Approach

Keep status derivation reusable and side-effect free. At the `change_continue()` boundary, first derive the ordinary status and inspect `nextRecommended`. For an actionable phase, instantiate `ChangeConfigAdministrator` with the repository root, validate the repository configuration, and call `get_context_by(nextRecommended)` to obtain the typed context. Attach that context to the returned immutable status. For `resolve-blockers`, attach no context.

Use a dedicated `configContext` field rather than repurposing `phaseInstructions`: the returned value is structured data, while `phaseInstructions` is an existing nullable string contract. Preserve every existing field and its meaning.

For example, when `nextRecommended` is `prd`, `ChangeConfigAdministrator.get_context_by("prd")` returns the canonical `change_propose` context. The exact JSON fragment appended by `change-continue` is:

```json
"configContext": {
  "phase": "change_propose",
  "phase_rules": ["First rule", "Second rule"]
}
```

The fragment above is the only new field. The following is a complete representative final `change-continue` response. The fields from `schemaName` through `blockedReasons` are the stable existing `ChangeStatus` fields (with their names and meanings unchanged); `schemaVersion` advances to `2` to advertise the additive shape. The final `configContext` field is new and contains the phase-specific value returned through `get_context_by`:

```json
{
  "schemaName": "ai-harness.change-status",
  "schemaVersion": 2,
  "changeName": "auth-rework",
  "changeRoot": ".ai-harness/changes/auth-rework",
  "artifactPaths": {
    "exploration": [".ai-harness/changes/auth-rework/exploration.md"],
    "prd": [],
    "design": [],
    "specs": [],
    "tasks": [],
    "implementation": [],
    "validation": []
  },
  "artifacts": {
    "explore": "done",
    "prd": "missing",
    "design": "missing",
    "specs": "missing",
    "tasks": "missing",
    "implement": "missing",
    "validate": "missing",
    "archive": "missing"
  },
  "taskProgress": {
    "total": 0,
    "completed": 0,
    "pending": 0,
    "allComplete": false
  },
  "dependencies": {
    "explore": "all_done",
    "prd": "ready",
    "design": "blocked",
    "specs": "blocked",
    "tasks": "blocked",
    "implement": "blocked",
    "validate": "blocked",
    "archive": "blocked"
  },
  "relationships": {
    "parent": null,
    "siblings": [],
    "children": []
  },
  "phaseInstructions": null,
  "nextRecommended": "prd",
  "blockedReasons": [],
  "configContext": {
    "phase": "change_propose",
    "phase_rules": ["First rule", "Second rule"]
  }
}
```

`configContext` is additive and nullable. Increment `schemaVersion` from `1` to `2` for all `ChangeStatus` responses so consumers can detect the shape change; `change-new` emits the version-2 shape with `configContext: null`. Existing field names, including `phaseInstructions`, remain present and unchanged. Consumers that support version 1 continue to have an explicit compatibility signal rather than silently receiving a changed schema.

Configuration warnings such as unknown phase keys remain non-halting. A validation result with `is_valid == false`, a missing config, or a parse/read failure is translated into `ChangeStoreError`. The CLI exits non-zero, writes the human-readable error through its existing stderr path, and writes no status JSON to stdout. A successful call must reach `get_context_by`; implementation must not substitute direct YAML access. Because freshness is required, each invocation creates/uses a fresh read path and never reuses a prior context.

Update both the source orchestrator prompt and its rendered expectation, plus active CLI-contract documentation, to show the version-2 field and require forwarding the context only when a routable phase exists.

## Affected Areas

- `src/ai_harness/modules/harness/change.py`: response model and continuation-time config integration.
- `src/ai_harness/commands/change.py`: serialization/type documentation and established error boundary, if needed.
- `src/ai_harness/modules/change_config/module.py`: consumed as the required public seam; no new public method is required.
- `src/ai_harness/resources/change-agent/change-orchestrator.md`: response contract and forwarding instruction.
- `expected/change-orchestrator.md`: rendered expectation synchronization.
- `.ai-harness/specs/agent-cli-contracts/orchestrator-cli-contract.md`: version-2 `ChangeStatus` contract.
- `tests/test_change.py`, `tests/test_change_config.py`, and `tests/test_renderers.py`: domain, CLI, error, freshness, and prompt-contract coverage.

## Risks

- Adding a field changes an externally visible JSON schema; version 2 and retention of all prior fields make the change explicit and additive.
- Validation followed by `get_context_by` may read the file twice, leaving a narrow edit race. This change prioritizes strict failure behavior and use of the required public seam; no caching or direct parser bypass is acceptable.
- Existing exhaustive prompt/test assertions may assume identical `change-new` and `change-continue` examples. Both must move to the version-2 field set while clearly showing null versus populated context.
- Rules are typed as a tuple internally but serialized as an array; acceptance tests must assert the public JSON representation.
- Treating `resolve-blockers` as a configured phase would misroute work; the explicit null contract avoids that ambiguity.

## Rollback Plan

Remove continuation-time configuration loading and the `configContext` field, restore `schemaVersion` to `1`, and revert orchestrator contract/prompt updates. No persisted change artifacts or configuration migrations are introduced, so rollback requires no data transformation.

## Dependencies

- Existing `ChangeConfigAdministrator.validate_config()` and `get_context_by()` behavior and phase alias map.
- Existing file-backed `ChangeStatus.nextRecommended` routing.
- Dataclass-to-JSON serialization at the command boundary.
- Repository `.ai-harness/config.yml` initialized with the supported config schema.

## Success Criteria

- For each routed value `explore`, `prd`, `design`, `specs`, `tasks`, `implement`, `validate`, and `archive`, `change-continue` calls `get_context_by` with that routed value and returns the matching canonical `phase` in `configContext`.
- `prd` returns `phase: "change_propose"`; `implement` returns `phase: "change_implementor"`; `archive` returns `phase: "change_archiver"`.
- Configured rules appear in `phase_rules` as a JSON array in source order, including an empty array when the routed phase has no rules.
- Editing `.ai-harness/config.yml` between two invocations causes the second response to contain the edited rules, proving no cross-invocation cache is used.
- A `resolve-blockers` response succeeds with `configContext: null` and does not request context for `resolve-blockers`.
- `change-new` does not load phase context and returns `configContext: null`.
- All successful `ChangeStatus` responses report `schemaVersion: 2`, retain all version-1 fields with unchanged meanings, and include the new nullable `configContext` field.
- The documented contract includes both the exact appended `configContext` fragment and a parseable, complete representative `change-continue` response in which `nextRecommended: "prd"`, `phase: "change_propose"`, and the ordered `phase_rules` values agree.
- Missing config, unreadable or malformed YAML, and schema-invalid config each produce a non-zero `change-continue` exit, a useful stderr message through the established error path, and no partial status JSON on stdout.
- Unknown config phase keys may produce validation warnings but do not prevent context delivery for a valid routed phase.
- The orchestrator prompt and rendered expectation document the exact JSON shape and direct the orchestrator to forward the returned context to the sub-agent selected by `nextRecommended`.
- Focused domain/CLI tests and renderer contract tests pass, including routing, serialization, freshness, blocked state, compatibility shape, and all configuration error cases.
