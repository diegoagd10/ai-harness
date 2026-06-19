# Proposal: Handoff — Deepening 1: Rename `Target.GENERIC` → `Target.AGENTS` and absorb "always-installed" into `install_targets`

## Intent

`install_targets` leaks the "agents always installed" rule across three locations: a private `_with_generic` helper, a docstring precondition on the caller, and e2e comments re-narrating the rule. Deleting `_with_generic` does not concentrate the rule — the docstring and comments survive as dead knowledge. The enum value `"generic"` is internal jargon the user never sees; their filesystem shows `.agents/AGENTS.md`. Deepen `install_targets` to own the rule internally and rename the enum to match what the user sees.

## Scope

### In Scope

- **Deepening**: `install_targets` guarantees agents-on-top internally; delete `_with_generic`; remove the docstring precondition.
- **Rename**: `Target.GENERIC` → `Target.AGENTS`, value `"generic"` → `"agents"` — every reference across `src/`, `tests/`, `e2e/`.
- **CLI**: `parse_targets(raw, *, allowed=None)` — install passes `allowed={CLAUDE, COPILOT, OPENCODE}`; help text updated; `-o agents` rejected with a loud error.
- **README**: minor prose adjustment for the renamed enum (line 4).

8 files: `models.py`, `operations.py`, `commands/__init__.py`, `commands/install.py`, `commands/uninstall.py`, `tests/test_install.py`, `e2e/install_lifecycle.py`, `e2e/uninstall_lifecycle.py` (all under `src/ai_harness/` except the test/e2e paths).

### Out of Scope

- `uninstall_targets` body — manifest is the source of truth; no mirror rule.
- Manifest migration code — dev-only break, no production manifests exist (locked decision #8).
- README narrative rewrites beyond the rename — the change is self-documenting through the code.
- Wizard UX changes — no `wizard.py` exists.

### Non-Goals

- No silent fallback for invalid `-o` (locked decision #4).
- No deprecation alias for `_with_generic` — delete it.
- No new `_ensure_agents` helper (locked decision #10).

## Capabilities

### New Capabilities

- `install-targets`: the `Target` enum, `install_targets` semantics (agents always included), `parse_targets` allowed-target validation, and the `InstallManifest` / `installed.json` schema contract.

### Modified Capabilities

None — no existing spec covers the `Target` enum or manifest schema.

## Approach

Inline the rule inside `install_targets` as a one-liner prepend. Avoid extract-method; deleted code stays deleted. Rename is mechanical: s/`Target.GENERIC`/`Target.AGENTS`/g and s/`"generic"`/`"agents"`/g across the 8 listed files, with manual review to exclude English-adjective uses in prompt/skills resources. `parse_targets` gains a keyword-only `allowed` set; install callers pass the restricted set, uninstall callers pass the default (all valid values including `AGENTS`).

## Affected Packages/Modules

`ai_harness.modules.harness.models` (enum rename), `ai_harness.modules.harness.operations` (deepen `install_targets`), `ai_harness.commands` (add `allowed` kwarg), `ai_harness.commands.install` (delete `_with_generic`), `ai_harness.commands.uninstall` (docstring update), `tests/` + `e2e/` (mechanical rename across 3 files), `README.md` (L4 prose).

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Old `installed.json` with `"generic"` fails to parse on uninstall | Medium | Dev-only break (locked decision #8); single PR revert |
| `install_targets([Target.OPENCODE])` now implicitly includes agents — existing test only asserts OpenCode paths, not agent absence | Low | Add explicit `.agents/AGENTS.md` assertion in the opencode-only unit test |
| `parse_targets` currently has no `allowed` parameter — install must reject `-o agents` while uninstall must still accept it | Low | CLI test for rejected `-o agents`; uninstall path passes default `allowed` |

## Rollback Plan

Single PR revert. Internal change + test fixtures. No production users, no shipped manifests to migrate.

## Dependencies

None.

## Success Criteria

- [ ] `install_targets([])` installs only agents (all agent paths written, no CLI provider files).
- [ ] `install_targets([Target.CLAUDE])` installs agents + claude, in that order.
- [ ] `ai-harness install -o agents` exits nonzero with a clear error.
- [ ] `ai-harness uninstall -o agents` succeeds (uninstall still accepts all targets).
- [ ] All 19 `Target.GENERIC` references renamed to `Target.AGENTS`.
- [ ] All 10 `"generic"` string-literal manifest/target references renamed to `"agents"`; English-adjective uses untouched.
- [ ] `_with_generic` no longer exists.
- [ ] Unit + e2e suites pass (uv run pytest; e2e/docker-test.sh).
