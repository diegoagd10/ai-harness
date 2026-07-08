# Spec — Test Prompt Decoupling Seam Contract

## Body-superset containment

`tests/test_install.py::test_install_claude_rendered_body_matches_template_verbatim` keeps the install/render coverage seam but stops treating renderer output as byte-identical to bundled prompt resources.

Required assertion pattern:

```python
assert template_body in rendered_body, f"{name}: rendered body does not include template body"
```

This applies to both subagent templates and the orchestrator skill branch.

## Discovery-driven smoke

`tests/test_renderers.py` should validate resource packaging and native rendering without asserting prompt prose.

Required checks:

- Resource smoke uses `discover_agent_names()` as the source of truth.
- Resource smoke asserts `len(names) >= 9`.
- For each discovered name, a same-name `change-agent/{name}.md` template exists and has non-whitespace body.
- For each discovered name, `load_agent_metadata(name)` returns metadata with a non-empty description.
- Native render smoke is parametrized over `AgentCli.CLAUDE`, `AgentCli.OPENCODE`, and `AgentCli.COPILOT`.
- Native render smoke renders `change-archiver` with `home=tmp_path` and `overrides={}`.
- Native render smoke asserts exactly one artifact, frontmatter starting with `---\n`, and non-empty body after frontmatter.

## Non-goals

- Do not assert prompt prose fragments, command wording, result-envelope wording, exact agent names, or exact metadata/template parity.
- Do not edit production code, prompt resources, or metadata files.
