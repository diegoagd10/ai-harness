# Proposal: Prune Installer Over-Engineering

## Intent

The installer subsystem carries dead code, dead config/fields, and duplication that inflate maintenance surface. Most critically, the production install path writes e2e fixtures into a gitignored `resources/generated/` tree, and the Docker e2e passes ONLY because of that side effect — production code exists to feed tests. Cut all of it. No change to what end users get installed.

## Scope

### In Scope (11 verified findings, grouped)
- **A. Manifest/installer core:** unify 4 near-identical backup/conflict blocks (#5); delete unused `frontmatter_source` field (#6); delete `DirArtifact.merge_mode`/`merge_preserve` (#7).
- **B. Dead code:** delete dead `install_permissions`/`compute_required_rules`/`_parse_frontmatter_tools` + unused `re` import (#2); delete `get_skills()`/`Skill` dataclass + `dataclass` import (#3); remove test-only `catalog.py` constants (#4).
- **C. Dedupe:** one shared `_metadata_to_frontmatter` serializer (#8); per-installer `_assets()` builder (#9); inline `_phase_with_instructions` (#10).
- **D. Gated cut:** delete `_write_fixtures`/`_write_fixture`/`_GENERATED_DIR` from all three installers AND rewrite the e2e to self-compose expected content. Remove `generated/` tree + `.gitignore:10-11` (#1).
- **E. Wizard:** remove YAGNI `a`/`i` bindings (`_invert`/`_select_all`) + unused `Separator` import (#11).

### Out of Scope (Non-Goals)
- `compat.py` / Go-compat JSON layer — untouched.
- Installed artifact contents and target paths — unchanged.
- SDD or wizard behavior beyond removing dead `a`/`i` bindings.

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `agent-clis-installer` — removes the "Generated Fixtures for E2E" requirement; installers no longer write a build-time `resources/generated/` tree, and e2e self-composes expected content. All other findings are pure internal cleanup with no spec-level behavior change.

## Approach

Atomicity rule for #1: install-code deletion and e2e rewrite MUST land in the same change. With `generated/` gitignored, removing fixture-writing without rewriting the e2e breaks Docker immediately. The e2e self-composes by importing the shared `_metadata_to_frontmatter` (#8), `_METADATA`, `_build_opencode_config`, and `_build_hook_json` from production — single source of truth, no magic-string duplication. Do Group D last, after C lands the shared serializer.

Finding 4 decision: **delete the constants from `catalog.py` and inline path literals in the tests that need them.** They are not production contract; a shared test helper would just relocate dead coupling.

strict_tdd implication: guard tests for deleted code/fields (e.g. `frontmatter_source` ignore-tests, `compute_required_rules` tests, fixture tests) MUST be removed in the SAME step as the code they guard — no orphaned red.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `installers/{claude,copilot,opencode}.py` | Modified | Remove fixture-writers; dedupe assets + frontmatter |
| `installers/installer.py`, `manifest.py` | Modified | Unify file blocks; drop dead fields |
| `catalog,permissions,wizard,rendering.py` | Modified | Delete dead code + unused imports |
| `resources/generated/`, `.gitignore` | Removed | Drop gitignored fixture tree |
| `e2e/`, `tests/` | Modified | Self-compose e2e; remove guard tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| e2e breaks if #1 cut lands alone | High | Atomic landing; e2e imports production serializer/`_build_*` |
| Orphaned guard tests under strict_tdd | Med | Delete code + guard tests in same step |
| Unused imports after cuts | Med | Remove `re`, `dataclass`, `Separator` with their cut |

## Rollback Plan

Deletion-heavy change. Each group (A–E) is an independent commit; revert any single commit to restore. Group D is the only coupled unit — revert restores both `_write_fixtures` and the prior e2e source constants together. Full rollback: `git revert` the change's commit range; no data migration, no installed-artifact state to undo.

## Dependencies

- Group D depends on Group C's shared frontmatter serializer existing first.

## Success Criteria

- [ ] All listed dead code, fields, config, and imports removed.
- [ ] `uv run pytest` green with guard tests removed (no orphaned assertions).
- [ ] `e2e/docker-test.sh` green WITHOUT any `resources/generated/` tree.
- [ ] No production code path writes test fixtures.
- [ ] Installed artifact contents and target paths byte-identical to before.
