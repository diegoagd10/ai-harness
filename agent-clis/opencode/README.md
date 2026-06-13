# agent-clis/opencode

Faithful copy of the **OpenCode** SDD (Spec-Driven Development) configuration that
the internal `ai-harness` CLI installs. Staged here so we can study/adapt it
**without touching the repo's main `skills/`**.

This mirrors what `ai-harness install` writes into `~/.config/opencode/`.

## How the pipeline works

A single **primary** agent orchestrates; everything else is a **hidden subagent**
delegated to via OpenCode's native `task` tool. There is no custom runtime — the
whole pipeline is prompts + `opencode.json` config.

```
gentle-orchestrator (primary)
  └─ task tool ─▶ sdd-init → sdd-explore → sdd-propose ─┬─▶ sdd-spec ─┐
                                                        └─▶ sdd-design ┴─▶ sdd-tasks
                  ─▶ sdd-apply → sdd-verify → sdd-archive
  judgment ─▶ jd-judge-a ∥ jd-judge-b (blind, parallel) → jd-fix-agent → re-judge
  review   ─▶ review-risk / -readability / -reliability / -resilience (R1–R4)
```

The orchestrator never works inline; it asks a session **preflight** (interactive vs
auto, artifact backend, PR strategy, review budget), enforces **hard gates** between
phases, and a **review-workload guard** before implementing.

## Layout

| Path | Purpose |
|---|---|
| `opencode.json` | The whole agent graph: `gentle-orchestrator` (primary) + 17 hidden subagents (10 SDD phases, 3 judgment-day, 4 reviewers). Prompts are `{file:...}` references; only the short judgment/reviewer prompts stay inline. |
| `AGENTS.md` | Global persona / system prompt applied to all agents. |
| `sdd-orchestrator.md` | The primary orchestrator prompt, referenced by `gentle-orchestrator` via `{file:{{HOME}}/.config/opencode/sdd-orchestrator.md}`. |
| `blocks/*.md` | Source blocks that control repeated or generated prompt sections. Tests ensure the final prompt files stay synchronized with these blocks. |
| _(generated)_ slash commands | The five user-facing entrypoints (`/sdd-new`, `/sdd-continue`, `/sdd-status`, `/sdd-init`, `/sdd-onboard`) are no longer staged here. They live once as platform-neutral templates at the repo root `prompts/commands/*.md`; `ai-harness install` generates the OpenCode-specific files into `~/.config/opencode/commands/`. Phases are not commands — the orchestrator drives them as hidden subagents. |
| `plugins/*.ts` | OpenCode plugin `model-variants.ts` (model profiles). |

## `{{HOME}}` placeholder

`opencode.json` references subagent prompts with absolute paths using a literal
`{{HOME}}` placeholder, e.g.:

```json
"prompt": "{file:{{HOME}}/.config/opencode/prompts/sdd/sdd-init.md}"
```

`ai-harness` substitutes `{{HOME}}` with the real home dir at install time.

The phase prompts these refs point at are **not** stored in this folder. They live once at
the repo root in `prompts/sdd/*.md` (the single source of truth, shared across the opencode,
claude, and copilot installs) and are written into `~/.config/opencode/prompts/sdd/` at
install time. To run this copy directly, point the `{file:...}` refs at your repo-root
`prompts/sdd/` or drop those files into `~/.config/opencode/prompts/sdd/` yourself.

## Source

Assembled from the internal `ai-harness` OpenCode assets, with `opencode.json` /
`AGENTS.md` taken from its generated fixtures.
