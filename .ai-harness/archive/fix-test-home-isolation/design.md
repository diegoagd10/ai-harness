# Design — fix-test-home-isolation

## Context

Renderer and metadata tests in `tests/test_renderers.py` currently mix two meanings behind the same default call shape: most tests want pure template rendering, while a small override-store family intentionally wants the production disk-read path. Because `render_artifacts()` and `get_agent_metadata()` can fall back to `Path.home()` when `home`/`overrides` are omitted, default calls make test results depend on the developer's real `~/.ai-harness/overrides.json`.

This design keeps production code untouched. The deep seam is the existing renderer API's environment boundary: tests must make the desired environment explicit at every relevant call site. The implementation should be mechanical, local to `tests/test_renderers.py`, and must not replace disk-store coverage with in-memory overrides.

The requested parent design file was not present at `/home/diegoagd10/Projects/ai-harness/.ai-harness/worktrees/fix-unit-tests/.ai-harness/changes/fix-renderers-shim-deletion/design.md`; this contract uses the locked architecture plus `prd.md` and `exploration.md`.

Pre-change ambient-read shape:

```text
test body / helper
    |
    | render_artifacts() / get_agent_metadata()
    v
renderer default arguments
    |
    | home omitted, overrides omitted/None
    v
Path.home()
    |
    v
real ~/.ai-harness/overrides.json
```

Post-change explicit-isolation shape:

```text
pytest tmp_path
    |
    v
test body / helper
    |
    | normal tests: home=tmp_path, overrides={}
    | store tests:  home=tmp_path, overrides=None/omitted
    v
renderer / metadata seam
    |
    v
tmp_path/.ai-harness/overrides.json only when disk-store behavior is under test
```

## Deep modules

### Renderer Environment Test Seam
- Seam: Calls from `tests/test_renderers.py` into `render_artifacts()` and `get_agent_metadata()`.
- Interface: Every in-scope call must choose exactly one of these argument contracts:
  - Explicit isolation: `home=tmp_path, overrides={}`.
  - Override-store disk semantics: `home=tmp_path` and `overrides=None` or omitted, preserving the test's disk-read assertion.
  - No-touch: already isolated tests keep their existing explicit `home`/`overrides` or isolated `HOME` setup.
- Hides: Production fallback behavior, local developer override-store contents, and whether a test reaches the renderer directly or through administrator helpers.
- Depth note: This is deep because one tiny call-site contract removes an environment-dependent class of failures without changing renderer internals or duplicating override-store logic in tests.

### Helper-propagated Home Boundary
- Seam: `_change_orchestrator_body`, `_native_change_orchestrator_body`, and `_native_change_implementor_body` in `tests/test_renderers.py`.
- Interface: Each helper accepts an isolated home path and forwards it into its internal render call:
  - `_change_orchestrator_body(..., home: Path) -> str` calls `render_artifacts(..., home=home, overrides={})`.
  - `_native_change_orchestrator_body(cli: AgentCli, home: Path) -> str` calls `ADMINISTRATORS[cli].render_artifacts(home=home, overrides={})`.
  - `_native_change_implementor_body(cli: AgentCli, home: Path) -> str` calls `ADMINISTRATORS[cli].render_artifacts(home=home, overrides={})`.
- Hides: The transitive renderer calls inside prompt-body helpers and the wide set of tests that consume their rendered body strings.
- Depth note: The helper seam earns its keep because deleting it would scatter render lookup and body extraction logic through dozens of tests; adding `home` here fixes the hidden ambient read once and forces callers to declare isolation.

### Override-store Disk Semantics
- Seam: Tests whose purpose is to prove auto-loading or `overrides=None` behavior.
- Interface: Use `tmp_path: Path`; pre-write `tmp_path / OVERRIDES_REL` only when the scenario needs store contents; call with `home=tmp_path` and preserve omitted/`None` overrides exactly where that path is the assertion.
- Hides: Store file placement, malformed-store fixture setup, missing-store behavior, and the distinction between explicit in-memory overrides and disk auto-load.
- Depth note: This is deep because it protects the production disk-read behavior as a named test seam instead of flattening all tests to `overrides={}` and silently deleting coverage.

## Internal collaborators

- `tmp_path` fixture: pytest-owned temporary home provider. It is not mocked; it composes with the existing renderer API to redirect disk access.
- `OVERRIDES_REL`: existing relative override-store path. Tests write `tmp_path / OVERRIDES_REL` for controlled disk fixtures only in override-store scenarios.
- `_find_pair(...)`: existing artifact lookup helper. It remains an internal collaborator behind body helpers and should not become a separate isolation seam.

## Seam map

```text
tests/test_renderers.py
    |
    +-- direct render/metadata tests
    |       +-- explicit isolation: home=tmp_path, overrides={}
    |       +-- store semantics:   home=tmp_path, overrides=None/omitted
    |
    +-- body helper tests
            +-- helper(home=tmp_path)
                    +-- render_artifacts(home=home, overrides={})
```

### Test seam contract table

| Bucket | Tests/helpers in scope | Exact argument pattern |
| --- | --- | --- |
| Explicit isolation | `test_render_agents_claude_returns_agents_and_skill` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_render_agents_opencode_returns_agents_under_agent_dir` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_render_agents_honours_explicit_names` | Add `tmp_path: Path`; keep names arg; add `home=tmp_path, overrides={}`. |
| Explicit isolation | `test_render_agents_writes_change_orchestrator_to_native_agent_dirs` | Add `tmp_path: Path`; every native CLI render call uses `home=tmp_path, overrides={}`. |
| Explicit isolation | `test_claude_subagents_have_name_and_model` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_claude_output_has_no_mode_field` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_claude_change_subagents_have_no_tools_field` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_claude_subagents_have_no_color` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_change_orchestrator_body_has_human_review_gate_heading` | Add `tmp_path: Path`; every CLI-loop render call uses `home=tmp_path, overrides={}`. |
| Explicit isolation | `test_change_orchestrator_body_gate_names_every_artifact` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_change_orchestrator_body_gate_requires_explicit_confirmation` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `_change_orchestrator_body` | Change helper to accept `home: Path`; internal render uses `home=home, overrides={}`. |
| Explicit isolation | `_change_orchestrator_body` callers: `test_change_orchestrator_body_interactive_stop_after_every_delegated_phase`, `test_change_orchestrator_body_continue_after_prd_authorizes_design_only`, `test_change_orchestrator_body_ambiguous_checkpoint_does_not_approve`, `test_change_orchestrator_body_requires_exact_skill_md_path_injection`, `test_change_orchestrator_body_locks_auto_interactive_phase_gate`, `test_change_orchestrator_body_session_mode_hard_gate_before_delegation`, `test_change_orchestrator_body_unspecified_mode_defaults_to_interactive_and_caches`, `test_change_orchestrator_body_cached_interactive_survives_continue`, `test_change_orchestrator_body_cached_auto_runs_gatekeeper_before_next_phase`, `test_change_orchestrator_body_missing_artifact_blocks_auto_progression`, `test_change_orchestrator_body_scope_drift_blocks_auto_progression`, `test_change_orchestrator_body_bad_next_recommended_blocks_auto_progression`, `test_change_orchestrator_body_failed_gatekeeper_never_launches_dependent_phase`, `test_change_orchestrator_body_interactive_continue_cannot_chain_auto`, `test_contract_orchestrator_pause_requires_stop_ask_wait`, `test_contract_orchestrator_approval_requires_phase_scope`, `test_contract_orchestrator_explore_must_wait_before_prd_same_turn`, `test_contract_orchestrator_continue_after_prd_authorizes_design_only`, `test_contract_orchestrator_auto_requires_explicit_or_cached_selection`, `test_contract_orchestrator_auto_gatekeeper_requires_all_four_checks`, `test_contract_orchestrator_launch_dedup_session_log_required` | Add `tmp_path: Path`; call `_change_orchestrator_body(home=tmp_path)` while preserving any existing `cli` argument. |
| Explicit isolation | `test_phase_prompts_expose_shared_result_envelope` | Add `tmp_path: Path`; every dict-comprehension render call uses `home=tmp_path, overrides={}`. |
| Explicit isolation | `test_change_orchestrator_body_frontmatter_parity_after_body_only_edits` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_opencode_frontmatter_includes_mode` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_opencode_frontmatter_includes_permission_where_configured` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_opencode_change_implementor_has_no_permission_block` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_change_orchestrator_frontmatter_uses_meta` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})` and `get_agent_metadata(..., home=tmp_path, overrides={})`. |
| Explicit isolation | `test_opencode_subagents_have_no_color` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_render_agents_copilot_returns_agent_files` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})`. |
| Explicit isolation | `test_copilot_frontmatter_has_name_and_description_only` | Add `tmp_path: Path`; call `render_artifacts(home=tmp_path, overrides={})` and `get_agent_metadata(..., home=tmp_path, overrides={})`. |
| Explicit isolation | `test_render_agents_copilot_honours_explicit_names` | Add `tmp_path: Path`; keep names arg; add `home=tmp_path, overrides={}`. |
| Explicit isolation | `test_change_archiver_renders_on_every_native_agent_cli` | Add `tmp_path: Path`; every native CLI render call uses `home=tmp_path, overrides={}`. |
| Explicit isolation | `_native_change_orchestrator_body` | Change helper to accept `home: Path`; internal administrator render uses `home=home, overrides={}`. |
| Explicit isolation | `_native_change_orchestrator_body` callers: `test_change_orchestrator_body_four_entry_classes_in_canonical_order`, `test_change_orchestrator_body_entry_class_boundary_statement_present`, `test_change_orchestrator_body_hard_triggers_present`, `test_change_orchestrator_body_canonical_english_trigger_phrases`, `test_change_orchestrator_body_canonical_spanish_trigger_phrases`, `test_change_orchestrator_body_bare_flow_exclusion`, `test_change_orchestrator_body_similarity_check_tokens`, `test_change_orchestrator_body_no_external_prior_art_paths`, `test_change_orchestrator_body_hard_gate_heading_preserved`, `test_change_orchestrator_body_no_new_cli_commands_or_flags`, `test_change_orchestrator_body_similarity_check_gated_to_entry_classes_3_and_4`, `test_change_orchestrator_body_similarity_check_three_branch_contract`, `test_change_orchestrator_body_inlines_commit_format_directive`, `test_renderer_parity_change_orchestrator_has_commit_format_directive` | Add `tmp_path: Path` after `cli` where needed; call `_native_change_orchestrator_body(cli, home=tmp_path)`. |
| Explicit isolation | `_native_change_implementor_body` | Change helper to accept `home: Path`; internal administrator render uses `home=home, overrides={}`. |
| Explicit isolation | `_native_change_implementor_body` callers: `test_change_implementor_body_applies_injected_commit_format`, `test_change_implementor_body_blocks_on_missing_directive`, `test_change_implementor_body_blocks_on_unknown_placeholder`, `test_renderer_parity_change_implementor_has_substitution_rule`, `test_renderer_parity_change_implementor_has_missing_directive_error` | Add `tmp_path: Path` after `cli` where needed; call `_native_change_implementor_body(cli, home=tmp_path)`. |
| Explicit isolation | `test_all_three_administrators_render_polymorphically` | Existing isolated render stays isolated; add `home=tmp_path, overrides={}` to the trailing `get_agent_metadata("change-explorer")` call. |
| Override-store disk semantics | `test_get_agent_meta_without_overrides_is_unchanged` | Already uses `tmp_path`; keep `home=tmp_path`; keep omitted/`None` overrides semantics. |
| Override-store disk semantics | `test_template_meta_not_mutated_by_overrides_across_calls` | Keep third default-path metadata call as `home=tmp_path` with omitted overrides; do not convert that assertion to `{}`. |
| Override-store disk semantics | `test_get_agent_meta_auto_loads_override_store_from_home` | Keep `home=tmp_path`; pre-write `tmp_path / OVERRIDES_REL`; keep omitted/`None` overrides. |
| Override-store disk semantics | `test_get_agent_meta_auto_load_missing_store_is_noop` | Keep `home=tmp_path`; keep omitted/`None` overrides. |
| Override-store disk semantics | `test_get_agent_meta_auto_load_partial_override_preserves_others` | Keep `home=tmp_path`; pre-write partial store; keep omitted/`None` overrides. |
| Override-store disk semantics | `test_get_agent_meta_auto_load_unknown_override_agent_ignored` | Keep `home=tmp_path`; pre-write unknown-agent store; keep omitted/`None` overrides. |
| Override-store disk semantics | `test_get_agent_meta_auto_load_malformed_store_raises` | Keep `home=tmp_path`; pre-write malformed store; keep omitted/`None` overrides. |
| Override-store disk semantics | `test_render_agents_auto_loads_override_store_from_home` | Keep `home=tmp_path`; pre-write `tmp_path / OVERRIDES_REL`; keep omitted/`None` overrides. |
| Override-store disk semantics | `test_render_agents_byte_identical_when_no_overrides` | Add `tmp_path: Path`; both comparison calls use `home=tmp_path`; preserve omitted/default and `overrides=None` distinction. |
| Override-store disk semantics | `test_render_agents_copilot_byte_identical_when_no_overrides` | Add `tmp_path: Path`; both comparison calls use `home=tmp_path`; preserve omitted/default and `overrides=None` distinction. |
| No-touch | `test_render_agents_explicit_overrides_skips_malformed_home_store`, `test_get_agent_meta_explicit_overrides_wins_over_store`, `test_claude_administrator_render_artifacts_returns_artifact_objects`, `test_claude_administrator_routes_primary_mode_to_skill`, `test_claude_administrator_routes_non_primary_mode_to_agent`, `test_claude_administrator_skill_frontmatter_description_only`, `test_claude_administrator_subagent_frontmatter_contains_name_model`, `test_claude_administrator_effort_override_propagates_to_frontmatter`, `test_claude_administrator_effort_null_drops_field`, `test_claude_administrator_get_agent_metadata_returns_typed_value`, `test_claude_administrator_get_agent_metadata_applies_overrides`, `test_opencode_administrator_renders_to_opencode_agent_dir`, `test_opencode_administrator_frontmatter_has_description_mode_model`, `test_opencode_administrator_missing_model_raises`, `test_opencode_administrator_reasoning_effort_emitted_when_set`, `test_opencode_administrator_reasoning_effort_null_is_omitted`, `test_opencode_administrator_explicit_permission_wins_over_caps`, `test_opencode_administrator_get_agent_metadata_resolves_overrides`, `test_opencode_administrator_empty_permission_omitted`, `test_copilot_administrator_renders_to_copilot_agent_dir`, `test_copilot_administrator_frontmatter_name_and_description_only`, `test_copilot_administrator_does_not_require_model_copilot`, `test_copilot_administrator_overrides_do_not_leak_extra_frontmatter`, `test_copilot_administrator_get_agent_metadata_resolves_overrides`, `test_operations_uses_artifact_install_path_for_writes` | Leave existing isolated `home=` / `overrides=` / fixture setup unchanged except incidental formatting caused by nearby edits. |

### Migration order

| Step | Scope | Rule |
| --- | --- | --- |
| 1 | Direct must-fix tests in file order | Add `tmp_path: Path` to each signature. |
| 2 | Direct must-fix calls | Pass `home=tmp_path, overrides={}` to every non-store `render_artifacts()` / `get_agent_metadata()` call in that test. |
| 3 | `_change_orchestrator_body` | Add `home: Path` to the helper, forward `home=home, overrides={}`, then update every caller to accept `tmp_path: Path` and pass `home=tmp_path`. |
| 4 | `_native_change_orchestrator_body` | Add `home: Path`, forward `home=home, overrides={}`, then update every parametrized caller to accept and pass `tmp_path`. |
| 5 | `_native_change_implementor_body` | Add `home: Path`, forward `home=home, overrides={}`, then update every parametrized caller to accept and pass `tmp_path`. |
| 6 | Override-store tests | Add or retain `home=tmp_path`; keep `overrides=None`/omitted only where disk-store behavior is the assertion. |
| 7 | Gate | Run `uv run pytest tests/test_renderers.py`, then `uv run ruff format --check tests/test_renderers.py` and `uv run ruff check tests/test_renderers.py`. |

### Risk-mitigation map

| PRD risk | Implementation rule |
| --- | --- |
| Multi-line `render_artifacts(...)` / `get_agent_metadata(...)` calls can be missed by regex. | Audit semantically after edits: every in-scope call must have either `home=tmp_path, overrides={}` or the documented store-semantics pattern; do not rely on single-line search only. |
| Shared helpers hide transitive render calls. | Migrate helper signatures before closing the task; every helper caller must pass `home=tmp_path`, so missing callers fail visibly instead of silently reading real HOME. |
| `Path.home()` / `HOME` tests are sensitive and `overrides=None` has coverage meaning. | Never convert override-store/equivalence tests to `overrides={}`; redirect only `home=tmp_path` and preserve fixture writes under `tmp_path / OVERRIDES_REL`. |

## Rejected alternatives

- Monkeypatch global `HOME` for the whole module: rejected because it hides which tests rely on disk-store loading and creates a broad fixture seam that can mask future ambient reads.
- Change production defaults to ignore `Path.home()` in tests: rejected because the PRD explicitly excludes production changes and the runtime disk-store behavior is real behavior under test.
- Replace every omitted/`None` override with `{}`: rejected because it deletes coverage for auto-loading and default-vs-`None` equivalence.
- Add a wrapper around `render_artifacts()` just for tests: rejected as a shallow seam that merely renames the existing renderer API while spreading another call convention through the file.

## Acceptance criteria checklist

- [ ] No production files are modified.
- [ ] Every explicit-isolation test above has `tmp_path: Path` and passes `home=tmp_path, overrides={}` at the relevant renderer/metadata call.
- [ ] `_change_orchestrator_body`, `_native_change_orchestrator_body`, and `_native_change_implementor_body` accept `home: Path` and forward `home=home, overrides={}`.
- [ ] Every caller of those three helpers passes `home=tmp_path`.
- [ ] The 10 override-store tests preserve omitted/`None` override semantics while using `home=tmp_path`.
- [ ] No test reads or writes the real `~/.ai-harness/overrides.json`.
- [ ] `uv run pytest tests/test_renderers.py` passes.
- [ ] `uv run ruff format --check tests/test_renderers.py` and `uv run ruff check tests/test_renderers.py` pass.
