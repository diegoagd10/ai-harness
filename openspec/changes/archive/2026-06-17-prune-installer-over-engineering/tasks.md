# Tasks: Prune Installer Over-Engineering

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~550-750 (deletion-heavy) |
| 400-line budget risk | High |
| 800-line budget | Within budget |
| Size exception needed | Pre-approved (auto / exception-ok) |
| Suggested work units | 5 (Groups C, A-core, B, D-atomic, E) |
| Delivery strategy | single-pr |
| Size exception | Yes |

Decision needed before apply: No
Maintainer-approved size exception: Yes
400-line budget risk: High

### Suggested Work Units (single PR; organizational only)

| Unit | Goal | Delivery | Notes |
|------|------|----------|-------|
| 1 | Group C: shared serializer + dedupe | single PR | foundation; serializer test first |
| 2 | Group A: installer/manifest dedup + dead fields | single PR | depends on Unit 1 |
| 3 | Group B+E: dead code/imports/wizard | single PR | independent of D |
| 4 | Group D: fixture cut + e2e self-compose | single PR | ATOMIC; depends on Unit 1; do LAST |
| 5 | Cleanup + full verification | single PR | depends on all |

## Phase 1: Foundation — Shared Serializer (Group C)

- [x] 1.1 RED: create `tests/test_frontmatter.py` asserting `metadata_to_frontmatter` emits `model:` for a claude `_METADATA` entry and omits it for a copilot entry.
- [x] 1.2 GREEN: create `src/ai_harness/artifacts/installers/frontmatter.py` with `metadata_to_frontmatter(m)` per design (model-when-present).
- [x] 1.3 REFACTOR: in `claude.py` and `copilot.py`, import the shared serializer; delete the duplicated `_metadata_to_frontmatter` (claude 158-182, copilot 165-178); keep tests green.

## Phase 2: Installer/Manifest Core (Group A)

- [x] 2.1 In `installer.py` add `_place_file(target, prepared, backup_suffix, conflict_suffix, console)` and `_remove_file(target, prepared, backup_suffix, console)`; collapse the 4 backup/conflict blocks to call them. Keep `test_installer.py` (15) green.
- [x] 2.2 In `installer.py` remove the always-true `merge_mode` guard and de-indent the dir body; update `test_installer.py:164` docstring mention (#7).
- [x] 2.3 In `manifest.py` delete `ComposedFileArtifact.frontmatter_source` (#6) and `DirArtifact.merge_mode`/`merge_preserve` + comments (#7); update docstrings.
- [x] 2.4 Delete guard tests in same step: `test_manifest.py` optional/ignored guards; `test_claude_installer.py:203-225`; `test_copilot_installer.py:187-209`. Run `uv run pytest`.

## Phase 3: Dead Code & Imports (Group B + E)

- [x] 3.1 In `permissions.py` delete `install_permissions` (193-210), `compute_required_rules` (86-97), `_parse_frontmatter_tools` (46-80), unused `re` import; keep `TOOL_TO_RULE`/`install_permissions_from_tools`; fix docstring. Delete `test_permissions.py` `compute_required_rules`+`install_permissions` groups and their imports (#2).
- [x] 3.2 In `catalog.py` delete `get_skills` (68-91), `Skill` (41-47), `dataclass` import; delete the 4 `get_skills`/`Skill` tests in `test_catalog.py` (#3).
- [x] 3.3 In `catalog.py` delete test-only SRC constants + `RESOURCES_DIR` (15-35); inline the path literals in `test_install.py`/`test_uninstall.py` where used (#4).
- [x] 3.4 In `rendering.py` inline `_phase_with_instructions` to a membership check (#10); confirm `test_rendering.py`/`test_cli_sdd.py` stay green.
- [x] 3.5 In `wizard.py` delete `_invert`/`_select_all`, `a`/`i` key bindings, `Separator` import, and stale docstring (#11). Run `uv run pytest`.

## Phase 4: Asset Builders (Group C cont.)

- [x] 4.1 In `claude.py` and `opencode.py` extract per-installer `_assets()` builder (#9); keep installer tests green.

## Phase 5: Gated Cut — Fixture Removal + E2E Self-Compose (Group D, ATOMIC)

> Single atomic group. Do NOT split: `resources/generated/` is gitignored and empty in Docker, so deleting writers without rewriting the e2e breaks Docker immediately.

- [x] 5.1 RED: rewrite e2e expected-content to self-compose from production — import `metadata_to_frontmatter`, `_METADATA`, `_build_opencode_config`, `_build_hook_json`; opencode.json via `json.dumps(_build_opencode_config(...), indent=2)+"\n"` then `.replace("{{HOME}}", home)`; Claude/inline via `metadata_to_frontmatter(_METADATA[name]).rstrip("\n")+"\n---\n"+body`. Remove e2e SRC constants (`OPENCODE_JSON_SRC`, `CLAUDE_AGENTS_SRC`, `CLAUDE_ORCHESTRATOR_SRC`, `COPILOT_AGENTS_SRC`, `COPILOT_HOOKS_SRC`).
- [x] 5.2 GREEN: delete `_GENERATED_DIR` + `_write_fixtures`/`_write_fixture` + call sites from `claude.py`, `copilot.py`, `opencode.py` (#1).
- [x] 5.3 Delete fixture guard tests in same step: `test_claude_installer.py:309-339`, `test_copilot_installer.py:325+`, `test_install.py:500-528`.

## Phase 6: Cleanup & Verification

- [x] 6.1 Delete `src/ai_harness/resources/generated/.gitkeep`; remove `.gitignore` lines 10-11 (`generated/*`, `!.gitkeep`); remove any `.dockerignore` `generated/` entry.
- [x] 6.2 Verify `uv run pytest` fully green (no orphan red, no removed-symbol references).
- [x] 6.3 Verify `e2e/docker-test.sh` green WITHOUT any `resources/generated/` tree present.
