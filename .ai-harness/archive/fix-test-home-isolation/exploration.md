# Exploration — fix-test-home-isolation

## Budget
142

LOC estimate: 68 ambient-read-affected tests/helper callers × 2 mechanical edits (add `tmp_path: Path`, pass `home=tmp_path` plus `overrides={}` where needed) = 136, plus ~6 lines for the three shared helper signatures/calls (`_change_orchestrator_body`, `_native_change_orchestrator_body`, `_native_change_implementor_body`).

Note: the requested Child A validation artifact was not present at `/home/diegoagd10/Projects/ai-harness/.ai-harness/worktrees/fix-unit-tests/.ai-harness/changes/fix-renderers-shim-deletion/validation.md`; the active worktree only has `fix-bad-unit-tests/` and `fix-test-home-isolation/`. This exploration therefore uses the parent exploration plus a direct AST/grep audit of `tests/test_renderers.py`.

## Affected Files
- `tests/test_renderers.py` — only implementation target; multiple tests call `render_artifacts()` / `get_agent_metadata()` without both `home=` and `overrides=`, and three helper functions hide additional ambient reads.
- `.ai-harness/changes/fix-test-home-isolation/exploration.md` — this read-only exploration artifact.

## Must-fix list
Direct call sites with neither `home=` nor `overrides=`:

- `test_render_agents_claude_returns_agents_and_skill` — line 62, `render_artifacts()`.
- `test_render_agents_opencode_returns_agents_under_agent_dir` — line 83, `render_artifacts()`.
- `test_render_agents_honours_explicit_names` — line 103, `render_artifacts([...])`.
- `test_render_agents_writes_change_orchestrator_to_native_agent_dirs` — lines 118-120, three native CLI `render_artifacts()` calls.
- `test_claude_subagents_have_name_and_model` — line 130, `render_artifacts()`.
- `test_claude_output_has_no_mode_field` — line 142, `render_artifacts()`.
- `test_claude_change_subagents_have_no_tools_field` — line 151, `render_artifacts()`.
- `test_claude_subagents_have_no_color` — line 160, `render_artifacts()`.
- `test_change_orchestrator_body_has_human_review_gate_heading` — line 193, `render_artifacts()` inside CLI loop.
- `test_change_orchestrator_body_gate_names_every_artifact` — line 202, `render_artifacts()`.
- `test_change_orchestrator_body_gate_requires_explicit_confirmation` — line 221, `render_artifacts()`.
- `_change_orchestrator_body` — line 248 helper; transitive ambient read for many body-contract tests.
- `test_phase_prompts_expose_shared_result_envelope` — line 431, `render_artifacts()` inside dict comprehension.
- `test_change_orchestrator_body_frontmatter_parity_after_body_only_edits` — line 742, `render_artifacts()`.
- `test_opencode_frontmatter_includes_mode` — line 764, `render_artifacts()`.
- `test_opencode_frontmatter_includes_permission_where_configured` — line 773, `render_artifacts()`.
- `test_opencode_change_implementor_has_no_permission_block` — line 787, `render_artifacts()`.
- `test_change_orchestrator_frontmatter_uses_meta` — lines 796 and 800, `render_artifacts()` and `get_agent_metadata()`.
- `test_opencode_subagents_have_no_color` — line 817, `render_artifacts()`.
- `test_render_agents_byte_identical_when_no_overrides` — lines 994-995, default call plus `overrides=None`; use `home=tmp_path` on both and keep `overrides=None` only where testing equivalence.
- `test_render_agents_copilot_returns_agent_files` — line 1429, `render_artifacts()`.
- `test_copilot_frontmatter_has_name_and_description_only` — lines 1449 and 1467, `render_artifacts()` plus `get_agent_metadata(name)`.
- `test_render_agents_copilot_byte_identical_when_no_overrides` — lines 1489-1490, default call plus `overrides=None`; use `home=tmp_path` on both and keep `overrides=None` only where testing equivalence.
- `test_render_agents_copilot_honours_explicit_names` — line 1497, `render_artifacts([...])`.
- `test_change_archiver_renders_on_every_native_agent_cli` — lines 1774-1776, three native CLI `render_artifacts()` calls.
- `_native_change_orchestrator_body` — line 1842 helper; transitive ambient read for parametrized orchestrator body tests.
- `_native_change_implementor_body` — line 2128 helper; transitive ambient read for parametrized implementor body tests.
- `test_all_three_administrators_render_polymorphically` — line 2413, `get_agent_metadata("change-explorer")` after an already-isolated render call.

Transitive helper callers that need `tmp_path` if the helpers are updated to accept `home: Path`:

- `_change_orchestrator_body(...)`: tests from lines 253-687 plus archive routing tests at 1784, 1797, and 1815.
- `_native_change_orchestrator_body(cli)`: parametrized tests at lines 1847-2098 and 2229.
- `_native_change_implementor_body(cli)`: parametrized tests at lines 2133-2262.

Explicit-overrides-but-missing-`home` call sites are not the primary ambient read path because `overrides` is non-`None`, but they are not fully isolated by the strict “pass both args” rule. Design should decide whether to add `home=tmp_path` uniformly to these too; examples include override-frontmatter tests around lines 975-1219, metadata override tests around lines 902-964 and 1233-1234, and explicit malformed-HOME bypass tests at lines 1387 and 1410.

## Already-isolated list
These already pass both `home=` and `overrides=` on all matching calls and should be left alone except for incidental formatting:

- `test_render_agents_explicit_overrides_skips_malformed_home_store`
- `test_get_agent_meta_explicit_overrides_wins_over_store`
- `test_claude_administrator_render_artifacts_returns_artifact_objects`
- `test_claude_administrator_routes_primary_mode_to_skill`
- `test_claude_administrator_routes_non_primary_mode_to_agent`
- `test_claude_administrator_skill_frontmatter_description_only`
- `test_claude_administrator_subagent_frontmatter_contains_name_model`
- `test_claude_administrator_effort_override_propagates_to_frontmatter`
- `test_claude_administrator_effort_null_drops_field`
- `test_claude_administrator_get_agent_metadata_returns_typed_value`
- `test_claude_administrator_get_agent_metadata_applies_overrides`
- `test_opencode_administrator_renders_to_opencode_agent_dir`
- `test_opencode_administrator_frontmatter_has_description_mode_model`
- `test_opencode_administrator_missing_model_raises`
- `test_opencode_administrator_reasoning_effort_emitted_when_set`
- `test_opencode_administrator_reasoning_effort_null_is_omitted`
- `test_opencode_administrator_explicit_permission_wins_over_caps`
- `test_opencode_administrator_get_agent_metadata_resolves_overrides`
- `test_opencode_administrator_empty_permission_omitted`
- `test_copilot_administrator_renders_to_copilot_agent_dir`
- `test_copilot_administrator_frontmatter_name_and_description_only`
- `test_copilot_administrator_does_not_require_model_copilot`
- `test_copilot_administrator_overrides_do_not_leak_extra_frontmatter`
- `test_copilot_administrator_get_agent_metadata_resolves_overrides`
- `test_operations_uses_artifact_install_path_for_writes`

Count: 26 functions.

## Override-store-specific tests
These intentionally exercise the disk-read path. Keep `overrides=None`/omitted semantics, but keep or add `home=tmp_path` so the store is redirected away from the real user HOME:

- `test_get_agent_meta_without_overrides_is_unchanged` — already uses `home=tmp_path`; missing store proves default metadata.
- `test_template_meta_not_mutated_by_overrides_across_calls` — third metadata call uses `home=tmp_path` with omitted overrides to prove absent store returns template defaults; first two explicit-overrides calls still lack `home` but do not read HOME.
- `test_get_agent_meta_auto_loads_override_store_from_home` — intentional store read at `tmp_path/.ai-harness/overrides.json`.
- `test_get_agent_meta_auto_load_missing_store_is_noop` — intentional missing-store path.
- `test_get_agent_meta_auto_load_partial_override_preserves_others` — intentional partial store read.
- `test_get_agent_meta_auto_load_unknown_override_agent_ignored` — intentional unknown-agent store read.
- `test_get_agent_meta_auto_load_malformed_store_raises` — intentional malformed store read.
- `test_render_agents_auto_loads_override_store_from_home` — intentional render-time store read.
- `test_render_agents_byte_identical_when_no_overrides` — intentionally compares omitted overrides to `overrides=None`; add `home=tmp_path` to both calls.
- `test_render_agents_copilot_byte_identical_when_no_overrides` — same comparison for Copilot; add `home=tmp_path` to both calls.

Count: 10 functions, including the two byte-identical tests that need HOME redirection while preserving `overrides=None` behavior.

## Plan
- Update direct default `render_artifacts()` tests in file order to accept `tmp_path: Path` and pass `home=tmp_path, overrides={}`.
- For direct default `get_agent_metadata()` calls, accept `tmp_path: Path` and pass `home=tmp_path, overrides={}` unless the test is explicitly about auto-loading the override store.
- Update `_change_orchestrator_body`, `_native_change_orchestrator_body`, and `_native_change_implementor_body` to accept `home: Path` and call `render_artifacts(..., home=home, overrides={})`.
- Update each helper caller to accept `tmp_path: Path` and pass it through to the helper; preserve existing `cli` parametrization.
- For override-store-specific tests, keep omitted/`None` overrides only where that behavior is the assertion, but always ensure `home=tmp_path` is present.
- Optionally, after the core ambient-read fix, add `home=tmp_path` to explicit-overrides tests for uniform isolation if design chooses strict “both args everywhere” consistency.

## Edge Cases
- Multi-line calls exist around lines 1235, 1324, 1364, 1387, 1410, 1523, 3066, 3211, and 3317; single-line regex can miss them.
- Helper functions hide many ambient reads; grepping only test function bodies undercounts failures.
- `overrides=None` is semantically meaningful: it enables disk store loading. Do not replace it with `{}` in tests whose point is default-vs-`None` equivalence or override-store loading.
- Tests that monkeypatch `HOME` at lines 1359, 1385, and 1408 are specifically checking HOME/store isolation; adding `home=tmp_path` is safe, but changing `overrides` semantics is not.
- Some call sites pass explicit `overrides={}` but no `home`; these do not read `Path.home()` today, but remain inconsistent with a strict full-isolation convention.

## Test Surface
- `uv run pytest tests/test_renderers.py` — primary gate for all changed call sites.
- `uv run pytest tests/test_renderers.py -k "override_store or no_overrides or render_agents"` — useful narrow gate for HOME override behavior.
- `uv run ruff format --check tests/test_renderers.py` and `uv run ruff check tests/test_renderers.py` — signature wrapping/import cleanliness after adding `tmp_path` params.

## Risks
- Under-counting from regex-only search is the main risk; AST search found 112 total matching call expressions and 28 owners with neither `home` nor `overrides`.
- Updating shared helper signatures creates wider mechanical churn than direct call-site counting suggests; missing one helper caller will cause immediate `TypeError` or leave an ambient read.
- Replacing `overrides=None` with `{}` in override-store-specific tests would remove coverage of the disk-read path.
- Adding `tmp_path` to heavily parametrized tests increases signature noise but should not affect parametrization.
- The Child A validation artifact was unavailable in this worktree, so the “smoking-gun” deferred failure list could not be cross-checked directly.

## semantic_facts
- budget: 142
- follow_up: Design should decide whether strict consistency requires adding `home=tmp_path` to explicit-overrides tests that already avoid HOME reads via non-`None` overrides; implementation must preserve `overrides=None` only for override-store/equivalence tests.
