# Design — fix-test-prompt-decoupling

## Context

This child change removes brittle prompt-prose coupling from renderer/install unit tests while preserving coverage for the seams that matter: installed output must include bundled template bodies, discovered change-agent resources must be package-complete enough to load, and the `change-archiver` template must render on every native agent CLI. Product behavior, prompt resources, metadata resources, and production rendering code are out of scope.

### Pre-change diagram — byte equality and keyword checks

```text
tests/test_install.py
  |
  | render Claude install artifact
  v
rendered body ----------------------+
                                    | byte equality / prefix
bundled template body --------------+

tests/test_renderers.py
  |
  +--> read change-agent prompt markdown
  |       |
  |       v
  |    assert exact contract keywords / command prose / envelope wording
  |
  +--> compare exact metadata JSON set <-> exact template markdown set
```

Hidden problem: tests cross the resource seam and lock editorial wording, file-set exactness, and renderer wrapping details that are not the behavior under test.

### Post-change diagram — containment and discovery smoke

```text
tests/test_install.py
  |
  | render Claude install artifact
  v
rendered body ----------------------+
                                    | body-superset containment
bundled template body --------------+

tests/test_renderers.py
  |
  +--> discover_agent_names()
  |       |
  |       +--> assert count floor >= 9
  |       +--> assert same-name template exists and body is non-empty
  |       +--> load_agent_metadata(name).description is non-empty
  |
  +--> render change-archiver on Claude/OpenCode/Copilot
          |
          +--> assert one artifact, frontmatter, non-empty body
```

The post-change tests keep the same behavioral pressure but move the assertion boundary to stable seams: containment, discovery/loadability, and structural render shape.

### Test seam contract table

| Target | Action | Exact assertion pattern after change |
| --- | --- | --- |
| `tests/test_renderers.py::test_change_agent_prompt_set_contains_expected_contract_keywords` | Delete | No replacement prompt keyword assertions. Coverage moves to discovery smoke count, template existence, non-empty body, and metadata loadability. |
| `tests/test_renderers.py::test_change_archiver_prompt_runs_cli_command_and_commits_once` | Delete | No command prose assertions. Native smoke only asserts structural render shape for `change-archiver`. |
| `tests/test_renderers.py::test_change_archiver_body_ignores_unrelated_product_dirtiness` | Delete | No unrelated-dirtiness prose assertions. Do not replace with different archiver wording checks. |
| `tests/test_renderers.py::test_change_archiver_result_envelope_includes_archive_commit_and_blocked_errors` | Delete | No result-envelope prose assertions. Structural smoke remains frontmatter plus non-empty body. |
| `tests/test_renderers.py::test_agent_metadata_has_one_json_file_per_change_agent_template` | Delete | No exact metadata/template set parity. Discovery smoke asserts each discovered name has a same-name template and loadable metadata. |
| `tests/test_install.py::test_install_claude_rendered_body_matches_template_verbatim` | Rewrite | `assert template_body in rendered_body, f"{name}: rendered body does not include template body"` for subagents and orchestrator skill rendering. |
| `tests/test_renderers.py::test_change_agent_resources_smoke_have_metadata_and_body` | Add | `names = discover_agent_names()`; `assert len(names) >= 9`; per name: same-name `change-agent/{name}.md` exists, body `.strip()` is truthy, `load_agent_metadata(name).description` is truthy. |
| `tests/test_renderers.py::test_change_archiver_renders_on_native_agent_clis` | Add or reshape | Parametrize `AgentCli.CLAUDE`, `AgentCli.OPENCODE`, `AgentCli.COPILOT`; render with `home=tmp_path`, `overrides={}`; assert `len(artifacts) == 1`, `content.startswith("---\n")`, and body after frontmatter is non-empty. |

### Migration order

1. Rewrite `tests/test_install.py:951` first. This is lowest risk because it preserves the existing coverage shape and only relaxes exact/prefix matching into body containment. Gate: `uv run pytest tests/test_install.py`.
2. Delete the five exact prompt-content/resource-exactness tests by test name, not line number. Gate: `uv run pytest tests/test_renderers.py` to catch accidental adjacent-test damage.
3. Add the discovery-driven resource smoke check and add or reshape the native archiver render smoke. Gate: `uv run pytest tests/test_renderers.py tests/test_install.py`.
4. Run final implementation gates: `uv run pytest`, `uv run ruff format --check .`, and `uv run ruff check .`.

### Risk-mitigation map

| PRD risk | Implementation rule |
| --- | --- |
| Accidentally deleting unrelated Child A shim-deletion or Child B home-isolation tests | Delete only the five exact test names listed in scope; do not bulk-delete by region or stale line number. |
| Recreating coupling with exact prompt fragments, exact agent names, or exact parity | New tests may assert only discovered names, `>= 9` count floor, same-name template existence, non-empty body, loadable metadata, frontmatter, and non-empty rendered body. |
| Smoke too loose and broken packaging slips through | For every discovered name, check same-name markdown template existence, non-whitespace template body, and metadata description loaded via production loader. |
| Reading user configuration during smoke rendering | Render with explicit `home=tmp_path` and `overrides={}`. |
| Duplicating existing native archiver smoke coverage | Reshape the existing native CLI archiver smoke when present; add a new one only if no equivalent exists. |
| Leaving unused imports after deletion | Run ruff format check and ruff check after targeted pytest gates. |

### Acceptance criteria checklist

- [ ] The five named locked tests are removed from `tests/test_renderers.py` and no prompt-prose assertion replaces them.
- [ ] `test_install_claude_rendered_body_matches_template_verbatim` uses `assert template_body in rendered_body` for both subagent and orchestrator skill branches.
- [ ] `test_change_agent_resources_smoke_have_metadata_and_body` uses `discover_agent_names()`, asserts `len(names) >= 9`, and validates template existence, non-empty template body, and loadable metadata description per discovered name.
- [ ] `test_change_archiver_renders_on_native_agent_clis` covers Claude, OpenCode, and Copilot with `home=tmp_path` and `overrides={}`.
- [ ] No production source, prompt markdown, prompt metadata JSON, or resource package content changes.
- [ ] Targeted and final gates pass: renderer/install pytest, full pytest, ruff format check, and ruff check.

## Deep modules

### Body containment assertion

- Seam: `tests/test_install.py::test_install_claude_rendered_body_matches_template_verbatim`, at the boundary between bundled template bodies and installed/rendered files.
- Interface: one invariant: `template_body in rendered_body`, with the existing per-template `name` used only for diagnostic failure messages.
- Hides: frontmatter normalization, renderer-added headers, appended notes, and future wrapping around the template body.
- Depth note: This is deep because one tiny assertion preserves the useful invariant—template body survives rendering—while hiding all renderer decoration details that previously leaked through equality/prefix checks.

### Change-agent resource smoke

- Seam: `tests/test_renderers.py::test_change_agent_resources_smoke_have_metadata_and_body`, driven by `discover_agent_names()` and `load_agent_metadata(name)`.
- Interface: discovered agent names are the source of truth; tests require a minimum population (`>= 9`), a same-name markdown template, non-empty template text, and metadata with a non-empty description.
- Hides: exact agent set, editorial prompt content, metadata JSON file-set parity, metadata schema details already covered elsewhere, and future additions to the agent catalog.
- Depth note: This earns its seam by concentrating package-completeness coverage behind production discovery/loading APIs instead of spreading exact resource-set assumptions through tests.

### Native archiver render smoke

- Seam: `tests/test_renderers.py::test_change_archiver_renders_on_native_agent_clis`, parametrized across `AgentCli.CLAUDE`, `AgentCli.OPENCODE`, and `AgentCli.COPILOT`.
- Interface: `ADMINISTRATORS[cli].render_artifacts(["change-archiver"], home=tmp_path, overrides={})` returns exactly one artifact whose content starts with YAML frontmatter and has a non-empty body after frontmatter.
- Hides: agent-specific output paths, prompt prose, command wording, archive contract wording, user-home overrides, and rendered body internals.
- Depth note: The seam is deep because it tests native renderer compatibility with a three-CLI matrix through one structural contract rather than coupling to any one prompt body.

## Internal collaborators

- `discover_agent_names()` — production discovery collaborator used as the catalog source. It is not mocked; the smoke test covers it transitively with packaged resources.
- `load_agent_metadata(name)` — production metadata loader used only for loadability and description presence. The test avoids duplicating lower-level JSON schema assertions.
- `importlib.resources.files("ai_harness.resources") / "change-agent"` — package-resource accessor for same-name template existence/body checks. It remains an internal collaborator, not a separate public test seam.
- `ADMINISTRATORS` and `AgentCli` — production native administrator registry and CLI enum. The smoke test uses the real implementations with isolated `tmp_path` home and empty overrides.

## Seam map

```text
tests/test_install.py
  -> installed/rendered Claude artifact
  -> bundled template body
  -> Body containment assertion

tests/test_renderers.py
  -> discover_agent_names()
  -> package template lookup by discovered name
  -> load_agent_metadata(name)
  -> Change-agent resource smoke

tests/test_renderers.py
  -> AgentCli matrix
  -> ADMINISTRATORS[cli].render_artifacts(..., home=tmp_path, overrides={})
  -> Native archiver render smoke
```

Only three public test seams remain: containment, discovery/loadability, and structural renderability. Everything else is an internal collaborator exercised transitively.

## Rejected alternatives

- Keep byte-equality or prefix assertions and update expected outputs. Rejected because this preserves the shallow seam: renderer decoration and prompt body bytes remain exposed to install tests.
- Replace deleted tests with different keyword/prose assertions. Rejected because it merely moves coupling from one list of phrases to another and fails the deletion test.
- Assert the exact discovered agent list or exact metadata/template parity. Rejected because future valid agents would break tests; a count floor plus per-discovered-resource loadability is deeper.
- Mock discovery, metadata loading, or administrators in the smoke tests. Rejected because the goal is resource packaging/render wiring coverage; mocking would test only the test harness.
- Add a new duplicate native archiver render test when an equivalent exists. Rejected because duplicated seams increase maintenance without increasing coverage; reshape existing coverage when present.
