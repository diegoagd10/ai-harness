# Model/effort overrides live in an override store merged at render time

`set-models` lets a user rewrite the model and effort of the loop agents per
Agent CLI. The values do **not** edit the installed rendered agent files
directly (install is byte-identical on reinstall, so any in-place edit would be
silently reverted) and do **not** mutate the `_AGENT_META` source constant
(wrong layer; fails for a pip-installed package). Instead the wizard writes
`~/.ai-harness/overrides.json`, which `get_agent_meta` deep-merges over the
template defaults at render time, then re-renders the installed agents for that
one CLI. This keeps a single source of truth, makes the result reproducible
across reinstalls, and preserves the existing byte-identical-reinstall property
when no override is set (effort is omitted from frontmatter until configured).

## Consequences

- The loop-orchestrator on Claude Code is rendered as a *skill*, which carries
  no `model`/`effort`. So `set-models -o claude` configures only explorer,
  implementor, and validator; `-o opencode` covers all four (the orchestrator is
  a `mode: primary` agent there). This is a hard limit of the target, not a
  choice.
- OpenCode model choices and their cost/reasoning metadata are read from the
  machine (`opencode models` for the available list, `~/.cache/opencode/models.json`
  for cost and the `reasoning` flag). If OpenCode is absent, `set-models -o opencode`
  errors and tells the user to install and configure OpenCode first — there is
  no static fallback list.
