# PRD — fix-test-prompt-decoupling

## Intent

Decouple the renderer and install unit tests from bundled prompt prose while preserving useful coverage for resource packaging, metadata loading, and native agent rendering. The change should make prompt wording editable without breaking unit tests that are meant to validate structure and wiring rather than exact contract language.

User-visible behavior should not change. This is a test-side-only change: installed/rendered artifacts, prompt content, production rendering behavior, home isolation behavior, and administrator APIs remain unchanged.

## Scope

### In

- Delete the five locked prompt/resource-coupled tests from `tests/test_renderers.py` by exact test name:
  - `test_change_agent_prompt_set_contains_expected_contract_keywords`
  - `test_change_archiver_prompt_runs_cli_command_and_commits_once`
  - `test_change_archiver_body_ignores_unrelated_product_dirtiness`
  - `test_change_archiver_result_envelope_includes_archive_commit_and_blocked_errors`
  - `test_agent_metadata_has_one_json_file_per_change_agent_template`
- Rewrite `tests/test_install.py::test_install_claude_rendered_body_matches_template_verbatim` so rendered bodies must contain the bundled template body instead of matching it byte-for-byte or by prefix.
- Add a discovery-driven resource smoke test, `test_change_agent_resources_smoke_have_metadata_and_body`, that verifies discovered change agents have non-empty templates and loadable metadata.
- Add or reshape a native CLI render smoke test, `test_change_archiver_renders_on_native_agent_clis`, parametrized across Claude, OpenCode, and Copilot, that validates structural render shape for `change-archiver` without asserting prompt prose.
- Keep tests isolated from the user system by using `tmp_path`, `monkeypatch`, and explicit `home=tmp_path` / `overrides={}` where rendering is exercised.

### Out

- Home-isolation cleanup beyond the two smoke checks in this child; that belongs to Child B and is already done.
- Shim deletion or import migration work; that belongs to Child A and is already done.
- Adding, deleting, or editing prompt content.
- Adding new prompt resources or metadata files.
- Production code changes.
- Replacing prompt-prose assertions with different prompt-prose assertions, exact agent-set assertions, or exact metadata/template parity assertions.

## Capabilities

- Prompt-coupled test removal: five tests that assert exact prompt wording, command prose, envelope prose, or exact metadata/template file parity are deleted.
- Install body containment assertion: Claude install rendering verifies that every byte of the bundled template body is present in the rendered file while allowing renderer-added wrapping or extension.
- Discovery-driven resource smoke: discovered change-agent names are used as the source of truth, with a `len(discover_agent_names()) >= 9` floor plus per-name non-empty template and loadable metadata checks.
- Native archiver render smoke: `change-archiver` renders successfully for Claude, OpenCode, and Copilot and produces frontmatter plus a non-empty body, without checking archiver prompt text.
- User-system isolation: new render smoke coverage uses temporary home paths and explicit empty overrides so tests do not read or mutate the user's environment.

## Approach

Rewrite the install assertion first because it preserves an existing seam while only relaxing the body comparison. Replace:

```python
assert rendered_body == template_body
assert rendered_body.startswith(template_body)
```

with containment assertions of the form:

```python
assert template_body in rendered_body, f"{name}: rendered body does not include template body"
```

Apply this consistently for subagent templates and the orchestrator skill branch.

Delete the five locked tests by test name rather than by stale line numbers, because Child A shifted the current positions. Do not delete adjacent Child A/B coverage.

Add the resource smoke test around `discover_agent_names()` and `load_agent_metadata(name)`. The smoke should guard against empty or incomplete packaging while avoiding exact future agent-set coupling. It should assert the current minimum floor (`>= 9`), same-name markdown template existence, non-empty template body, and a non-empty loaded metadata description.

Add or reshape the `change-archiver` render smoke so it is parametrized over `AgentCli.CLAUDE`, `AgentCli.OPENCODE`, and `AgentCli.COPILOT`. Render with `home=tmp_path` and `overrides={}`. Assert exactly one artifact, `content.startswith("---\n")`, and a non-empty body after splitting frontmatter. Do not inspect command text, archive contract wording, result envelope field prose, or blocked-error prose.

Validate with targeted renderer/install tests first, then the full suite and ruff gates.

## Affected Areas

- `tests/test_renderers.py` — remove the five locked prompt/resource-coupled tests; add discovery-driven resource smoke; add or reshape native `change-archiver` render smoke.
- `tests/test_install.py` — relax `test_install_claude_rendered_body_matches_template_verbatim` from exact/prefix body matching to template-body containment.
- No production source files should change.
- No prompt resource files should change.

## Risks

- Accidentally deleting unrelated tests that cover Child A shim deletion or Child B home isolation. Mitigation: delete only the five exact test names listed in scope.
- Recreating the same coupling with new smoke checks by asserting exact prompt fragments, exact agent names, or exact metadata/template parity. Mitigation: use discovered names, a minimum count floor, non-empty body, and loadable metadata only.
- Making the smoke too loose so broken packaging slips through. Mitigation: check per discovered name that the same-name template exists, has non-whitespace content, and metadata loads with a description.
- Reading user configuration during render smoke checks. Mitigation: pass `home=tmp_path` and `overrides={}` explicitly.
- Duplicating an existing native CLI archiver smoke test. Mitigation: reshape the existing test when present instead of adding redundant coverage.
- Leaving unused imports after deleting prose tests. Mitigation: run ruff check/format checks after targeted pytest gates.

## Rollback Plan

Revert the test edits if the relaxed assertions hide a real regression. Restoring the deleted prompt-prose tests should be the last resort; prefer tightening structural smoke coverage without asserting prompt wording. Since no production behavior or resources are changed, rollback is limited to test files and has no data migration impact.

## Dependencies

- `discover_agent_names()` and `load_agent_metadata()` are available from `ai_harness.modules.harness.administrators` after Child A's shim deletion/import migration.
- `ADMINISTRATORS`, `AgentCli`, and render artifact behavior remain available for Claude, OpenCode, and Copilot administrators.
- Existing resource package layout keeps change-agent templates under `ai_harness.resources/change-agent/{name}.md`.
- Test isolation follows `AGENTS.md` and `CODING_STANDARDS.md`: use `tmp_path` / `monkeypatch`; tests must not touch the user system.
- Tooling: Python >=3.12, uv, pytest, ruff.

## Success Criteria

- The five locked tests are removed from `tests/test_renderers.py` and not replaced with prompt-prose assertions.
- `tests/test_install.py::test_install_claude_rendered_body_matches_template_verbatim` uses `assert template_body in rendered_body` for subagents and skill rendering.
- `test_change_agent_resources_smoke_have_metadata_and_body` exists and verifies `len(discover_agent_names()) >= 9`, non-empty same-name markdown templates, and loadable metadata descriptions.
- `test_change_archiver_renders_on_native_agent_clis` exists or is reshaped, is parametrized across Claude/OpenCode/Copilot, renders with `home=tmp_path` and `overrides={}`, and asserts frontmatter plus non-empty body only.
- No production code, prompt prose, prompt metadata, or prompt resource files are changed.
- Targeted gates pass: `uv run pytest tests/test_renderers.py` and `uv run pytest tests/test_install.py`.
- Final gates pass: `uv run pytest`, `uv run ruff format --check .`, and `uv run ruff check .`.
