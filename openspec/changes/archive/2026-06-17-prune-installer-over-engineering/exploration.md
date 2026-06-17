# Exploration: Prune installer over-engineering (11 findings)

Verification of an over-engineering audit against current code. Each finding
is classed CONFIRMED / NEEDS-ADJUSTMENT / REJECT with exact line ranges, every
caller/test impacted, and cross-cutting risk. No code changed.

## Current State

`ai-harness` builds per-CLI manifests (`claude.py`, `copilot.py`, `opencode.py`)
that a generic `installer.py` materializes into a synthetic HOME. Composition
joins a metadata-derived frontmatter string with a prompt body via
`frontmatter.rstrip("\n") + "\n---\n" + body` (`installer._prepare_composed_content`,
line 76). Unit tests live in `tests/` (pytest, pythonpath=src). E2E runs inside
Docker via `uv run inv test` (`e2e/Dockerfile` `CMD`, `e2e/tasks.py`).

Decisive discovery for Finding 1: `src/ai_harness/resources/generated/*` is
**gitignored** (`.gitignore:10-11`; only `.gitkeep` is tracked, confirmed via
`git ls-files`). So inside the Docker image (`COPY . /build`) `generated/` is
empty. The e2e source-path constants (`OPENCODE_JSON_SRC`, `CLAUDE_AGENTS_SRC`,
`COPILOT_AGENTS_SRC`, `COPILOT_HOOKS_SRC`, `CLAUDE_ORCHESTRATOR_SRC`) only
resolve because `_write_fixtures`/`_write_fixture` run during the real install
step and populate `generated/` as a side effect, which the e2e then reads back.
Production install writes test fixtures so the tests can read them — the core
over-engineering this change targets.

## Findings

### 1. DELETE e2e fixture-writing in the production install path — CONFIRMED (highest risk)

Exact current locations:
- `claude.py:364-427` (`_GENERATED_DIR` 366-368, `_write_fixtures` 370-427), called at `claude.py:229` inside `install()`.
- `copilot.py:363-417` (`_GENERATED_DIR` 365-367, `_write_fixtures` 369-417), called at `copilot.py:255`.
- `opencode.py:384-413` (`_GENERATED_DIR` 386-388, `_write_fixture` 390-413), called at `opencode.py:277`.
- Tree: `src/ai_harness/resources/generated/` (gitignored; runtime-populated).

What the e2e currently depends on (must be re-sourced if `generated/` goes away):
- `e2e/test_harness_lifecycle.py`
  - `OPENCODE_JSON_SRC = generated/opencode/opencode.json` (line 20), read in `_assert_opencode_json` (54-55) with `.replace("{{HOME}}", home)`.
  - `CLAUDE_AGENTS_SRC = generated/claude/agents` (line 22). SDD phases: reads fixture as **frontmatter-only** and composes `frontmatter.rstrip("\n") + "\n---\n" + body` itself (`_assert_claude_agents` 126-132). Inline JD/review agents: compared **byte-for-byte** against the fixture (147-150) — the fixture is the only source of the composed inline file.
  - `CLAUDE_ORCHESTRATOR_SRC = generated/claude/sdd-orchestrator/SKILL.md` (line 23) — imported but only used via existence check on the installed target (152-155); the SRC constant itself is not read for content.
- `e2e/test_copilot_cli_lifecycle.py`
  - `COPILOT_AGENTS_SRC` (27), `COPILOT_HOOKS_SRC` (28) — currently imported, but the assertions (`_assert_agents_installed`, `_assert_agent_frontmatter`, `_assert_hook_installed`) validate the **installed** files structurally (presence, YAML keys, hook allowlist) and never read the SRC constants for byte comparison. These two constants are effectively dead in the copilot e2e.

How the e2e can self-compose expected content (no `generated/` needed):
- opencode.json: import `_build_opencode_config` from `opencode.py`, `json.dumps(..., indent=2) + "\n"`, then `.replace("{{HOME}}", home)`. (Test would import production code — acceptable for e2e, or replicate the formula.)
- Claude SDD phases: already self-composing from `SDD_PROMPTS_SRC` + a frontmatter source. Replace the frontmatter source with `_metadata_to_frontmatter(_METADATA[name])` imported from `claude.py`.
- Claude inline JD/review agents: compose `_metadata_to_frontmatter(_METADATA[name]).rstrip("\n") + "\n---\n" + body` where body = `prompts/jd/<name>.md` or `prompts/review/<name>.md` (both dirs confirmed present). This reproduces exactly what `_prepare_composed_content` writes.
- Copilot: the two SRC constants can simply be dropped; assertions already validate installed files directly.

Risk: HIGH and the gating concern for the whole change. The cut and the e2e
rewrite MUST land together. If `_write_fixtures` is removed without rewriting the
e2e source constants, the Docker e2e breaks immediately (empty `generated/`).
Recommend: e2e imports the production `_METADATA` + `_metadata_to_frontmatter` +
`_build_opencode_config`/`_build_hook_json` so there is a single source of truth
and the composition formula is not duplicated as a magic string.

Unit tests to delete/adjust: `tests/test_claude_installer.py:309-339` (fixture
test), `tests/test_copilot_installer.py:325-331+`, `tests/test_install.py:500-528+`
(opencode fixture test). Also `.gitignore:10-11` and the `generated/` dir +
`.gitkeep` can be removed.

### 2. DELETE dead frontmatter-parsing permission path — NEEDS-ADJUSTMENT

- `install_permissions` (`permissions.py:193-210`): zero production callers. `claude.py` only imports `uninstall_permissions` (line 31) and calls `install_permissions_from_tools` (locally imported, line 270-272). CONFIRMED dead in production.
- `compute_required_rules` (`permissions.py:86-97`): only caller is the dead `install_permissions` (line 206) + tests. CONFIRMED dead.
- `_parse_frontmatter_tools` (`permissions.py:46-80`): only caller is `compute_required_rules` (line 93) + (transitively) tests. CONFIRMED dead.

Adjustment: the audit cited lines `46-97,193-210`. `_parse_frontmatter_tools` is
actually `46-80` (the audit's 81-85 are the section comment). Also the module
docstring (lines 1-17) advertises `compute_required_rules` and a "3 public
functions" surface — update it. `TOOL_TO_RULE` (30-38) is still used by the LIVE
`install_permissions_from_tools` (114), so KEEP. `re` import (line 23) becomes
unused once `_parse_frontmatter_tools` goes — remove it.

Tests to delete (`tests/test_permissions.py`, ~14 of 37): the `compute_required_rules`
groups (Task 1.2 lines 89-106, Task 1.3 lines 130-140, Task 1.4 lines 152-181) and
the `install_permissions` group (Task 1.8 lines 311-372). KEEP the
`_resolve_settings_path`, `_backup_settings`, `_merge_allow_rules`,
`_remove_managed_rules`, `uninstall_permissions`, and `install_permissions_from_tools`
tests. Update imports at lines 25-32 (drop `compute_required_rules`, `install_permissions`).

### 3. DELETE `get_skills()` + `Skill` dataclass — CONFIRMED

- `Skill` dataclass `catalog.py:41-47`; `get_skills` `catalog.py:68-91`.
- Production callers: NONE. Installers copy skills via `DirArtifact(source=catalog.get_root()/"skills")` (`claude.py:342-349`, `copilot.py:331-338`, `opencode.py:373-380`) — they never call `get_skills`.
- Only consumer: `tests/test_catalog.py` (`Skill` import line 9; tests at 26-79: `test_get_skills_returns_list_of_skill_instances`, `..._ignores_files_not_directories`, `..._when_no_skills_dir`, `test_skill_dataclass_is_frozen`).
- `from dataclasses import dataclass` (catalog.py:10) becomes unused after removal — drop it.
- Tests to delete: the four named above. Keep the other 4 catalog tests.

### 4. Unused catalog constants — MIXED (verify each)

- `JD_PROMPTS_SRC`, `REVIEW_PROMPTS_SRC`, `ORCHESTRATOR_PROMPTS_SRC` (`catalog.py:20-22`): zero references anywhere (grep clean). CONFIRMED dead — delete.
- `OPENCODE_JSON_TARGET` (34), `OPENCODE_SDD_PROMPTS_TARGET_DIR` (35), `AGENTS_MD_TARGETS` (24-28), `SKILLS_TARGET_DIRS` (29-33): used ONLY by `tests/test_uninstall.py` (imports line 8-14; uses 31,50,66,96,98,123,143). No production use. The spec can decide: delete the constants and inline literals in the test, OR keep as test-shared constants. Recommend delete from `catalog.py` and let the test own its own path literals (these are not production contract).
- `AGENTS_MD_SRC` (17): used by `tests/test_install.py` (10,27,215). Not production. Same call as above.
- `SKILLS_SRC` (18): used by `tests/test_install.py` (12,46,71) and `tests/test_uninstall.py` (13,49). Note e2e defines its OWN `SKILLS_SRC` (not the catalog one). Not production.
- `OPENCODE_SDD_PROMPTS_SRC` (19): used by `tests/test_install.py` (11,107,196), `tests/test_uninstall.py` (11,97). Not production. Also referenced by name in `test_catalog.py:93` only to assert a DIFFERENT constant (`OPENCODE_JSON_SRC`) raises ImportError.
- `RESOURCES_DIR` (catalog.py:15): the catalog module's own `RESOURCES_DIR` is the base for all the SRC constants above and is NOT imported by production install/uninstall commands — those define their own `RESOURCES_DIR` (`commands/artifacts/install.py:16`, `uninstall.py:16`). So catalog's `RESOURCES_DIR` is purely a test-fixture base. If all SRC constants leave, `RESOURCES_DIR` can leave too.

Net: every constant in `catalog.py:15-35` is consumed only by unit tests, never
by production. The proposal should decide whether to (a) delete all and inline
literals in tests, or (b) move the shared ones into a test helper. The catalog's
real production surface is just the four `ArtifactCatalog` methods (`get_root`,
`get_main_instructions`, `get_resource_dir`, and `get_skills` which #3 removes).

### 5. SHRINK four near-identical backup/conflict blocks — CONFIRMED

- install FileArtifact: `installer.py:100-109`; install ComposedFileArtifact: `installer.py:126-135` — byte-identical backup/conflict-rotation logic, differ only in `prepared` source (`_prepare_content` vs `_prepare_composed_content`).
- uninstall FileArtifact: `installer.py:191-197`; uninstall ComposedFileArtifact: `installer.py:210-216` — identical remove-if-match + restore-backup logic.
- Unify via a `(target, prepared, backup_suffix, conflict_suffix)` helper applied across both lists. `FileArtifact` and `ComposedFileArtifact` share `backup_suffix`/`conflict_suffix` defaults (manifest.py:19-20, 57-58), so a single `_place_file(target, prepared, ...)` and `_remove_file(target, prepared, ...)` covers both.
- Tests: `tests/test_installer.py` (15 tests) cover backup/conflict/restore behavior — they assert observable outcomes, so a pure refactor should keep them green. Verify no test patches the inline loop internals.

### 6. DELETE `frontmatter_source` field — CONFIRMED

- `manifest.py:55` (field) + docstring mention (48-49).
- Never SET by any installer (grep: only assertions). `_prepare_composed_content` (installer.py:74) uses `frontmatter_text` exclusively.
- Tests asserting it stays None / is ignored: `tests/test_manifest.py:50-67` (`test_composed_artifact_frontmatter_source_is_optional`), `tests/test_manifest.py:117-139` (`test_prepare_composed_content_ignores_frontmatter_source`), `tests/test_claude_installer.py:203-225`, `tests/test_copilot_installer.py:187-209`. These tests exist only to guard a field that should not exist — delete the field and these guard tests together. Docstrings referencing it (test_manifest.py:32,54,99) also adjust.

### 7. DELETE `DirArtifact.merge_mode` + `merge_preserve` future config — CONFIRMED

- `manifest.py:30-32` (field + two comment lines describing the unimplemented `merge_preserve`).
- Guard `if artifact.merge_mode == "replace_matching":` (`installer.py:150`) is always true — `merge_preserve` is never implemented or set. Removing the field lets the guard go and de-indents the install DirArtifact body (151-159).
- Tests: `tests/test_installer.py:164` (`test_dir_artifact_replace_matching`) references the mode in its docstring; the test constructs `DirArtifact` with the default. After removing the field, the test still works (behavior unchanged); just drop the mode mention. Confirm no test constructs `DirArtifact(merge_mode=...)` explicitly (grep showed none).

### 8. SHRINK duplicated `_metadata_to_frontmatter` — CONFIRMED (with a real divergence)

- `claude.py:158-182` includes a `model:` line; `copilot.py:165-178` omits it. Otherwise identical (`name`, `description`, `tools: [..]`).
- A shared serializer must be parameterized on whether `model` is emitted (or emit `model` only when the key is present in the metadata dict — claude metadata always has `model`, copilot never does, so "emit when present" unifies them cleanly without a flag).
- Extraction target: a small shared module (e.g. `installers/frontmatter.py` or a function in an existing shared module). This is the cross-cutting helper worth extracting — and it pairs with Finding 1, since the e2e should import the SAME serializer to avoid drift.
- No direct test imports `_metadata_to_frontmatter` today (grep clean). Installer tests assert the composed output, which stays identical.

### 9. SHRINK `ClaudeAssets`/`OpencodeAssets` built identically in install + uninstall — CONFIRMED

- Claude: `ClaudeAssets(...)` constructed identically at `claude.py:205-218` (install) and `claude.py:238-251` (uninstall).
- Opencode: `OpencodeAssets(...)` identical at `opencode.py:266-273` (install) and `opencode.py:282-289` (uninstall).
- Extract a private `_assets(self) -> ClaudeAssets` / `_assets(self) -> OpencodeAssets` builder per installer. Copilot already does this inline in `_build_manifest` (copilot.py:269-273), so it is fine.
- Tests: `tests/test_claude_installer.py` has an `_assets(root)` helper (used by fixture test); behavior is unchanged. Low risk.

### 10. SHRINK `_phase_with_instructions` — CONFIRMED

- `rendering.py:77-84`, single caller at `rendering.py:61`. A 3-line membership check (`if next_recommended in _PHASES_WITH_INSTRUCTIONS`).
- Inline as `phase = status.next_recommended if status.next_recommended in _PHASES_WITH_INSTRUCTIONS else None`.
- Tests: `tests/test_rendering.py` and `tests/test_cli_sdd.py` exercise `render_dispatcher` output (the "Next Phase Instructions" section). They assert rendered text, not the helper — a pure inline keeps them green. Verify neither test imports `_phase_with_instructions` directly (it is private; grep shows no external import).

### 11. YAGNI wizard `a`/`i` key bindings — CONFIRMED

- `wizard.py:118-126` (`_invert`, bound to `i`) and `wizard.py:128-141` (`_select_all`, bound to `a`).
- Over a fixed 3-item list (`AGENTS` from registry), and NOT advertised in `_FOOTER` (line 26: only ↑↓/jk/space/enter/esc). Dead UX.
- No test references `_invert`/`_select_all`/select-all/invert (grep clean across tests + e2e). `e2e/test_wizard_lifecycle.py` tests the `--all` bypass path, not interactive keys.
- Removal also lets the docstring of `_checkbox_bindings` (90-93: "invert, select all") shrink. `Separator` import (line 18) is used only by `_invert`/`_select_all` — after removal it becomes unused; remove it.

## Recommendation

Proceed. Findings 2,3,4,6,7,8,9,10,11 are low-risk independent cuts. Group them:
- **Group A (manifest/installer core):** 5,6,7 — touch `manifest.py` + `installer.py` + `tests/test_manifest.py`, `tests/test_installer.py`.
- **Group B (catalog/permissions dead code):** 2,3,4 — `catalog.py`, `permissions.py`, `tests/test_catalog.py`, `tests/test_permissions.py`, plus test-constant inlining in `tests/test_install.py`/`tests/test_uninstall.py`.
- **Group C (installer dedupe):** 8,9 — extract a shared frontmatter serializer (also consumed by e2e per Group D), per-installer `_assets()` builder.
- **Group D (the gated cut):** 1 — delete `_write_fixtures`/`_write_fixture`/`_GENERATED_DIR` AND rewrite the e2e to self-compose expected content (importing production `_METADATA`, the shared `_metadata_to_frontmatter`, `_build_opencode_config`, `_build_hook_json`). Must land atomically. Remove `generated/` tree + `.gitignore:10-11`.
- **Group E (wizard):** 11 — `wizard.py` only.

Do Group D LAST or in its own PR, after Group C lands the shared serializer the
e2e will import.

## Risks

- **Finding 1 e2e coupling (HIGH):** removing fixture-writing without rewriting the e2e source constants breaks the Docker suite immediately, because `generated/` is gitignored and empty in the image. The rewrite must compose expected content from prompt bodies + the shared frontmatter serializer + `_build_*` functions.
- **strict_tdd contract:** `openspec/config.yaml` sets `strict_tdd: true`. Deletions should remove the guard tests in the same step (red→green stays coherent) rather than leaving orphaned assertions.
- **Test-only catalog constants (Finding 4):** deleting them forces edits in `tests/test_install.py` and `tests/test_uninstall.py`; the proposal must decide inline-literals vs a test helper to avoid a second round of churn.
- **`re` import (permissions), `dataclass` import (catalog), `Separator` import (wizard):** each becomes unused after its respective cut — remove to keep linters green.

## Ready for Proposal

Yes. All 11 findings verified with exact line ranges and caller/test impact. The
proposal should sequence Group D (Finding 1) last/separately and mandate that the
e2e import the shared frontmatter serializer + `_build_*` functions so there is a
single source of truth for composed-artifact content.
