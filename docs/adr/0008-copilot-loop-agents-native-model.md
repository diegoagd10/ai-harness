# Copilot loop agents render name+description only; model stays native

The Copilot loop agent renderer writes only `name` and `description` into each
agent's YAML frontmatter — no `model`, `tools`, `user-invocable`, or
`disable-model-invocation`. The `set-models` wizard rejects `-o copilot` and
directs the user to the Copilot CLI's own model mechanism instead of building a
wizard, catalog, or override-store path for it.

## Context

Copilot CLI supports custom agents via `~/.copilot/agents/*.agent.md` files. The
loop's four agents (orchestrator, explorer, implementor, validator) install there
so the user can invoke the Loop with `/agent loop-orchestrator` and the three
subagents are visible and individually invocable via `/agent`.

However, the Copilot CLI's frontmatter support is narrower than VS Code's:
the CLI ignores the `model` field (github/copilot-cli#1354, #2758) and has no
public models catalog. Model selection in Copilot CLI is a single global model
set via `/model` or `~/.copilot/settings.json` — not a per-agent, per-file
concern.

## Decision

**The Copilot agent renderer emits only `name` and `description`.** It does not
read or require a copilot model entry in the agent metadata template
(`_AGENT_META`), unlike the Claude and OpenCode renderers which resolve a model
and effort per agent from the template defaults merged with the override store.

**`set-models -o copilot` stays rejected.** No wizard, no model catalog, no
per-agent override-store support is added for copilot. The rejection message
names the Copilot-native way: `/model` in the Copilot CLI or edit
`~/.copilot/settings.json`.

**No per-agent model for copilot in the override store.** The `overrides.json`
schema never grows a `copilot` key; the renderer never consults one. The
user-facing model story for Copilot is deliberately Copilot-CLI-native — not an
ai-harness concern.

## Rationale

- **Copilot CLI ignores the `model` frontmatter field.** Writing it would be
  misleading — the user would see a model name in the agent file and reasonably
  assume it is honored, but the CLI would ignore it.
- **No models catalog or per-agent model API.** Copilot CLI exposes a single
  global model (set via `/model` or `~/.copilot/settings.json`) and does not
  publish a list of available models or support per-agent model configuration.
- **The Copilot-native mechanism is already sufficient.** `/model` lists and
  switches the global model interactively; `settings.json` is the persistent
  equivalent. Building a wizard on top would duplicate native functionality
  without adding value.

### Evidence

- [github/copilot-cli#1354](https://github.com/github/copilot-cli/issues/1354)
  — frontmatter model field behavior
- [github/copilot-cli#2758](https://github.com/github/copilot-cli/issues/2758)
  — custom agent model configuration

## Considered options

| Option | Verdict |
|--------|---------|
| Emit `model` in frontmatter anyway | Rejected — field is ignored by CLI; writing it misleads the user |
| Build a Copilot model wizard in `set-models` | Rejected — no per-agent model API to write to; no catalog to list from |
| Let `set-models -o copilot` silently succeed as a no-op | Rejected — misleading; user thinks something changed when nothing did |
| **Reject with native guidance** | **Chosen** — honest, points to the right tool |

## Consequences

- Copilot loop agents carry only `name` and `description`. Adding
  `user-invocable` or `disable-model-invocation` later (if the CLI supports
  them) is a forward-compatible frontmatter addition that does not need an
  ADR — just a version guard and a renderer extension.
- `set-models -o copilot` will always reject. If Copilot CLI gains a per-agent
  model API in the future, this decision should be revisited.
- Related ADRs: [0002](0002-render-agents-per-cli.md) (per-CLI rendering),
  [0004](0004-model-effort-overrides.md) (override store for Claude/OpenCode
  models).
