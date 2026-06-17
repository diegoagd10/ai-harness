# Proposal: Copilot — hide phase subagents, expose only orchestrator

## Intent

The Copilot installer emits 16 agents today but all are user-pickable — no `user-invocable` flag. OpenCode and Claude already isolate subagents via `hidden: true` / `Agent` permissions. This change makes Copilot emit first-class custom-agent files per [GitHub's custom-agents doc](https://docs.github.com/en/copilot/reference/custom-agents-configuration), hiding 15 subagents from the picker and exposing only `sdd-orchestrator`.

## Scope

### In Scope
- Rename 16 agent files `{name}.md` → `{name}.agent.md` under `~/.copilot/agents/`
- Add per-agent frontmatter: `user-invocable`, `disable-model-invocation`, `target: github-copilot`, `model`
- Add `copilot_frontmatter()` serializer in `frontmatter.py` (separate from `metadata_to_frontmatter`)
- Add `agent` alias to orchestrator `tools`; keep `Task` as compatible alias
- Add `agents:` field to the orchestrator frontmatter listing exactly the 15 sub-agent names
  (VS Code field inherited by Copilot CLI / cloud agent via the `.agent.md` file format;
  see https://code.visualstudio.com/docs/copilot/customization/custom-agents and the
  `agents` row of the "Custom agent file structure" table — this is the declarative
  equivalent of OpenCode's `permission.task` allowlist)
- Update e2e/test assertions for `.agent.md` suffix and new frontmatter keys
- Keep `sdd-pre-tool-use.json` hook as defense-in-depth (unchanged)

### Out of Scope
- MCP servers, cloud-agent secrets, org-level agents
- Claude/OpenCode installer changes, new CLI flags, config rename

### In Scope (model pinning)
- Pin `sdd-orchestrator` to `model: GPT-5 mini`
- Pin all 15 subagents to `model: Claude Haiku 4.5`
- Both model names are the display names from https://docs.github.com/en/copilot/reference/ai-models/supported-models
  (the official custom-agents doc does not enumerate valid `model:` string values; the supported-models page is the only authoritative source)

## Capabilities

### Modified Capabilities
- `agent-clis-installer`: Copilot file extension, new frontmatter keys, separate serializer, orchestrator `agent` tool

## Approach

**Option C** from exploration: 16 `.agent.md` custom-agent files + hook defense-in-depth. Subagent tools lists unchanged per change intent.

New `copilot_frontmatter(metadata)` emits:

```yaml
---
name: sdd-explore
description: ...
tools: [Bash, Edit, View, Create, Glob, Grep, Read, Task]
target: github-copilot
user-invocable: false
disable-model-invocation: true
---
```

Orchestrator gets `user-invocable: true` and `tools: [agent, Task, Bash, ...]`. `metadata_to_frontmatter` stays untouched — zero Claude leakage.

## Affected Areas

| Area | Impact |
|------|--------|
| `src/ai_harness/artifacts/installers/copilot.py` | Target paths `.agent.md`, wire new serializer, orchestrator tools |
| `src/ai_harness/artifacts/installers/frontmatter.py` | Add `copilot_frontmatter()` |
| `tests/test_copilot_installer.py` | Extension + frontmatter-key assertions |
| `e2e/test_copilot_cli_lifecycle.py` | `.md`→`.agent.md`, new key checks, `f.stem`→name extraction |
| `openspec/specs/agent-clis-installer/spec.md` | New Copilot frontmatter scenarios |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `.md`→`.agent.md` breaks existing installs | Low | Manifest-driven uninstall cleans up; stale `.md` overwritten on reinstall |
| Cross-CLI frontmatter leakage | Low | Separate serializer; `metadata_to_frontmatter` untouched |
| e2e `f.stem` breaks with double extension | Med | Explicit suffix-strip helper |
| Hook/frontmatter allowlist drift | Low | Same `_SUBAGENT_NAMES` constant; tests assert alignment |

## Rollback Plan

`git revert` restores `.md` paths and drops new keys. Reinstall overwrites `.agent.md` with `.md` files.

## Dependencies

None.

## Open Questions Resolved

| # | Question | Resolution |
|---|----------|------------|
| 1 | `.md` or `.agent.md`? | `.agent.md` — matches GitHub convention and e2e docstrings |
| 2 | Keep hook? | Yes — defense-in-depth |
| 3 | Orchestrator body? | Keep `prompts/sdd/sdd-orchestrator.md` (task variant) |
| 4 | Tool case? | Keep TitleCase; Copilot aliases are case-insensitive |
| 5 | Model pinning? | Resolved — `sdd-orchestrator` → `GPT-5 mini`; 15 subagents → `Claude Haiku 4.5` (per https://docs.github.com/en/copilot/reference/ai-models/supported-models) |
| 6 | `target` value? | `github-copilot` on all 16 |
| 7 | Marker file? | No — manifest is truth |
| 8 | Serializer? | New `copilot_frontmatter()`, separate |
| 9 | Subagent `agent` tool? | Keep `Task` — per change intent, no harm |
| 11 | Orchestrator sub-agent allowlist? | Resolved — orchestrator frontmatter carries `agents: [sdd-explore, sdd-propose, ...]` (the 15 sub-agent names, single-sourced from `_SUBAGENT_NAMES`). Mechanism: VS Code `agents` field inherited by Copilot. Equivalent to OpenCode's `permission.task` allowlist but declarative and versioned with the agent file. |
| 10 | Test updates? | e2e gets frontmatter-key checks + `.agent.md` assertions |

## Acceptance Criteria

- [ ] Fresh install: 16 `.agent.md` files; only orchestrator has `user-invocable: true`
- [ ] Orchestrator `tools` includes `agent`; all 16 have `target: github-copilot`, `disable-model-invocation: true`
- [ ] Orchestrator frontmatter carries `model: GPT-5 mini`; each of the 15 subagents carries `model: Claude Haiku 4.5`
- [ ] Orchestrator frontmatter carries `agents: [<15 sub-agent names>]` (declarative sub-agent allowlist); the 15 sub-agent `.agent.md` files do NOT carry an `agents:` field
- [ ] Reinstall: byte-identical to first install
- [ ] Uninstall: zero `.agent.md` files under install root; hook removed
- [ ] Claude install: byte-identical to before (no Copilot key leakage)
- [ ] `sdd-pre-tool-use.json` unchanged, passes existing tests

## Review Workload

| Category | Est. lines | Risk |
|----------|-----------|------|
| `copilot.py` (paths + serializer + model + agents) | ~50 | Low |
| `frontmatter.py` (new fn + `model` + conditional `agents`) | ~40 | Low |
| Unit tests | ~50 | Low |
| e2e tests | ~70 | Med |
| Spec scenarios (incl. model pinning + agents allowlist) | ~60 | Low |
| **Total** | **~270** | Well within 800-line budget |
