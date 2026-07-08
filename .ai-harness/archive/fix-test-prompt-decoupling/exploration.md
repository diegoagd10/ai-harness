# Exploration — fix-test-prompt-decoupling

## Budget
-45

Reasoning: expected net LOC delta is negative. Deleting the five prompt/resource-coupled tests removes roughly 95-105 lines, rewriting the install assertion is a small assertion/docstring edit, and adding the discovery-driven smoke checks should add roughly 45-60 lines. Raw touched LOC is likely around 150, but the implementation should remove more prompt-prose assertions than it adds.

## Tests to delete
- `tests/test_renderers.py:1636` — `test_change_agent_prompt_set_contains_expected_contract_keywords`; asserts bundled prompt prose contains exact contract keywords such as `budget`, `nextRecommended`, `task-next`, CLI command strings, and forbidden legacy phrases. This couples tests to prompt body wording instead of renderer/resource shape.
- `tests/test_renderers.py:1757` — `test_change_archiver_prompt_runs_cli_command_and_commits_once`; reads `change-archiver.md` body and locks implementation prose around command, commit count, archive scope, and escalation wording.
- `tests/test_renderers.py:1779` — `test_change_archiver_body_ignores_unrelated_product_dirtiness`; reads `change-archiver.md` body and asserts exact prose/command fragments for unrelated dirtiness and staging verification.
- `tests/test_renderers.py:1800` — `test_change_archiver_result_envelope_includes_archive_commit_and_blocked_errors`; reads `change-archiver.md` body and locks envelope field wording such as `archive_commit`, `archive_paths`, and `errors`.
- `tests/test_renderers.py:2683` — `test_agent_metadata_has_one_json_file_per_change_agent_template`; cross-resource exact-set consistency check that pins metadata JSON files to visible template files and exact count. Replace with discovery-driven smoke coverage that each discovered name has a template body and loadable metadata.

## Test to rewrite
- `tests/test_install.py:951` — `test_install_claude_rendered_body_matches_template_verbatim`; keep the install/render seam but replace byte-identical/prefix body assertions with body-superset containment:

```python
assert template_body in rendered_body, f"{name}: rendered body does not include template body"
```

Apply the same assertion shape to the orchestrator skill branch, replacing the current `rendered_body.startswith(template_body)` assertion with `template_body in rendered_body`. This keeps coverage that installation includes the bundled template while allowing renderer-added body text around it.

## Affected Files
- `tests/test_renderers.py` — delete five prompt/resource-coupled tests; add discovery-driven smoke coverage for discovered agent names, non-empty templates, and loadable metadata; optionally reshape the existing native-CLI archiver render smoke into a parametrized check.
- `tests/test_install.py` — rewrite the Claude rendered-body assertion from exact/prefix equality to template containment.

## Smoke check shape
- Discovery-driven resource smoke:
  - call `discover_agent_names()` as the source of truth;
  - assert `len(names) >= 9` to guard against empty/incomplete packaging without pinning an exact future set;
  - for each name, assert a same-name `change-agent/{name}.md` exists;
  - assert the template body is non-empty after stripping whitespace;
  - assert metadata is loadable for the name, with at least a non-empty description.
- Optional native render smoke:
  - parametrize over `AgentCli.CLAUDE`, `AgentCli.OPENCODE`, and `AgentCli.COPILOT`;
  - render only `change-archiver` with `home=tmp_path` and `overrides={}`;
  - assert one artifact is produced, frontmatter exists, and rendered body after frontmatter is non-empty;
  - do not assert prompt text or archiver contract wording.

Sketch for design/tasks, not a production edit in this phase:

```python
def test_discovered_change_agents_have_templates_and_metadata() -> None:
    from importlib.resources import files

    from ai_harness.modules.harness.administrators import discover_agent_names, load_agent_metadata

    template_root = files("ai_harness.resources") / "change-agent"
    names = discover_agent_names()

    assert len(names) >= 9
    for name in names:
        template_path = template_root / f"{name}.md"
        assert template_path.is_file(), f"missing template for {name}"
        assert template_path.read_text(encoding="utf-8").strip(), f"empty template for {name}"
        assert load_agent_metadata(name).description


@pytest.mark.parametrize("cli", [AgentCli.CLAUDE, AgentCli.OPENCODE, AgentCli.COPILOT])
def test_change_archiver_renders_on_native_agent_clis(tmp_path: Path, cli: AgentCli) -> None:
    artifacts = ADMINISTRATORS[cli].render_artifacts(["change-archiver"], home=tmp_path, overrides={})

    assert len(artifacts) == 1
    assert artifacts[0].content.startswith("---\n")
    assert artifacts[0].content.split("---", 2)[2].strip()
```

## Plan
- Rewrite `tests/test_install.py:951` first because it is the least risky and preserves the existing install seam while relaxing only the body assertion.
- Delete the five locked prompt-content/resource-exactness tests from `tests/test_renderers.py`.
- Add the discovery-driven smoke test in `tests/test_renderers.py` using `discover_agent_names()` and the `>= 9` floor.
- Add or reshape the native CLI archiver render smoke so it verifies renderability on Claude/OpenCode/Copilot without prompt-body content assertions.
- Run targeted gates in design/tasks: `uv run pytest tests/test_renderers.py tests/test_install.py`, then full pytest and ruff checks during implementation validation.

## Edge Cases
- Existing line numbers have shifted after Child A: the locked `tests/test_renderers.py:1584` target is currently at line 1636, and the locked metadata target around 2599 is currently at line 2683. Implement by test name, not by stale line number.
- `test_discover_agents_excludes_underscore_prefixed_files` currently asserts the exact nine-agent list. This child does not need to delete it unless design broadens scope; the new smoke should avoid adding another exact-set assertion.
- `test_each_agent_metadata_json_decodes_and_has_required_fields` already validates metadata JSON syntax/required fields by file. The new smoke should cover loadability by discovered name rather than duplicating all schema assertions.
- Keep `home=tmp_path` and `overrides={}` in any render smoke so Child B home-isolation behavior remains respected and user-home overrides do not affect the result.

## Test Surface
- `uv run pytest tests/test_renderers.py` — verifies deleted prompt-content tests are gone and new smoke coverage passes.
- `uv run pytest tests/test_install.py` — verifies install-render body containment remains covered.
- `uv run pytest` — final regression gate because this change removes broad prompt/resource assertions.
- `uv run ruff format --check .` and `uv run ruff check .` — catches unused imports after deletions and parametrization changes.

## Risks
- Accidentally deleting a test that overlaps with Child A/B instead of only the locked prompt-content/resource-exactness tests. Mitigation: delete by exact test name and preserve home-isolation/import-migration coverage.
- Smoke check too tight: exact names, exact metadata/template parity, or prose fragments would recreate the prompt-coupling failure. Mitigation: use discovered names plus `>= 9`, existence, non-empty body, and loadable metadata only.
- Smoke check too loose: only checking count could miss a missing template or broken metadata. Mitigation: per-name template existence, non-empty body, and `load_agent_metadata(name).description`.
- Optional archiver render smoke may duplicate the existing `test_change_archiver_renders_on_every_native_agent_cli`; if kept, prefer parametrizing/reshaping that test rather than adding redundant coverage.

## semantic_facts
- budget: -45
- follow_up: Rewrite install body assertions first, delete exactly five named prompt/resource-coupled tests, then add discovery-driven smoke coverage with `len(discover_agent_names()) >= 9` plus per-name template and metadata checks. Keep Child A shim deletion and Child B home-isolation scope out of this child.
