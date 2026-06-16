# Proposal: GitHub Copilot CLI SDD adapter (`agent-clis/copilot-cli`)

## Intent

`ai-harness install` currently stages the full SDD agent graph for **OpenCode** (16 agents in `agent-clis/opencode/opencode.json`) and a partial graph for **Claude Code** (15 agents in `agent-clis/claude/agents/*.md` plus orchestrator skill). **GitHub Copilot CLI** only gets `.copilot/copilot-instructions.md` — no agents, no hooks, no skills. This change stages the full SDD graph (1 orchestrator + 8 phase + 3 judgment-day + 4 R1–R4 reviewers) as `*.agent.md` files under `~/.copilot/agents/`, adds JSON hooks under `~/.copilot/hooks/`, and wires skills to `~/.copilot/skills/`. The shared `prompts/sdd/*.md` remain the single source of truth, generic-ified so they work across all three adapters.

## Scope

### In Scope
- **16 `*.agent.md` files** under `src/ai_harness/resources/agent-clis/copilot-cli/agents/` (1 orchestrator + 8 phase + 3 JD + 4 reviewers). Frontmatter-only files; the body is composed at install time from the shared `prompts/sdd/*.md` (or extracted inline prompts for JD/reviewers).
- **JSON hooks** under `src/ai_harness/resources/agent-clis/copilot-cli/hooks/`. At minimum: `sdd-pre-tool-use.json` (delegation allowlist + path deny policy, fail-closed). Optional: `sdd-subagent-stop.json` and `sdd-agent-stop.json` to guard incomplete phases.
- **Adapter narrative doc** at `docs/agents/copilot/README.md` (new top-level `docs/agents/copilot/` directory) documenting the platform gaps, the layout, and the workarounds. Referenced from the root `README.md`.
- **Prompt generic-ification** of the 9 shared `src/ai_harness/resources/prompts/sdd/*.md` files: replace OpenCode-specific skill paths with the full set (`.agents/skills/`, `.claude/skills/`, `.copilot/skills/`, plus legacy `~/.config/opencode/skills/`), and replace "OpenCode's native `task` tool" with "the platform's native `task` tool" (3 occurrences in `sdd-orchestrator.md`).
- **`CopilotInstaller` extension** in `src/ai_harness/artifacts/installers/copilot.py` to compose agents at install, copy hooks, and install skills. Reuses the existing `FileArtifact`/`DirArtifact` and backup/restore infrastructure.
- **Catalog update** in `src/ai_harness/artifacts/catalog.py` to add `.copilot/skills` to `SKILLS_TARGET_DIRS` (only if the installer needs it; otherwise handled directly by the installer manifest).
- **E2E test contract** at `e2e/test_copilot_cli_lifecycle.py` (new) + `e2e/tasks.py` and root `tasks.py` wiring for an `inv copilot-cli-lifecycle` task. **First task in `sdd-apply` is writing these tests; they MUST fail (RED) before any implementation.** Mirrors `e2e/test_harness_lifecycle.py`.

### Out of Scope
- The orchestrator's `permission.task` allowlist drift (mentions `sdd-init`/`sdd-onboard` which don't exist as agents) — left for a follow-up change. This proposal does not touch `opencode.json` to avoid scope creep.
- Slash-commands gap (copilot-cli has no user-defined `/sdd-*`) — handled by natural-language triggers in the orchestrator body, which the existing shared prompt already supports.
- Per-agent `model` enforcement (copilot-cli ignores the field) — accepted functional gap; users configure globally via `/model` or `--model`.
- `hidden: true` analog (all 16 agents visible in `/agent` picker) — accepted UX gap; mitigated by consistent naming convention.
- End-to-end Docker run with a real copilot-cli binary (requires GitHub Copilot subscription, unavailable in CI) — covered by pytest + invoke e2e in the sandboxed HOME.

## Capabilities

### New Capabilities
- `agent-clis-copilot-cli`: the staged GitHub Copilot CLI SDD agent graph — 16 `*.agent.md` files under `resources/agent-clis/copilot-cli/agents/`, JSON hooks under `resources/agent-clis/copilot-cli/hooks/`, and an adapter README. Backed up and restored by the existing `FileArtifact`/`DirArtifact` infrastructure.

### Modified Capabilities
- `cli-sdd`: `ai-harness install`/`uninstall` gains copilot-cli agent + hook + skill wiring (compose-at-install for phase bodies, backup/`{{HOME}}` reuse).
- `prompts-sdd`: the 9 shared `prompts/sdd/*.md` files become transport-agnostic — they list all known skill paths and reference the platform's native `task` tool without naming OpenCode.

## Approach

Stage `resources/agent-clis/copilot-cli/agents/*.agent.md` as **frontmatter-only** files; the `prompt_body` is composed at install time by `CopilotInstaller`. For each agent:

1. Read the shared `prompts/sdd/<phase>.md` (or the extracted JD/reviewer markdown from the adapter) as the body.
2. Read the frontmatter template from the corresponding `*.agent.md` source file.
3. Concatenate: `frontmatter + "\n" + body` → write to `~/.copilot/agents/<name>.agent.md`.

Hook JSON files are copied as-is from the adapter source to `~/.copilot/hooks/`. The hook design is fail-closed: `preToolUse` matchers for `task` only allow delegation to the 15 actual subagent names; `bash`/`view`/`create`/`edit` matchers deny writes to sensitive paths (`~/.ssh/**`, `~/.aws/**`, `~/.config/gh/**`, `/etc/**`, `/tmp/**`, etc.) — mirroring the opencode `external_directory` deny list.

Tool name mapping (compose-time): `read → view`, `write → create`, `bash/edit/glob/grep/task` stay. MCP server tools use the `server/tool` naming.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/ai_harness/resources/agent-clis/copilot-cli/agents/*.agent.md`, `hooks/*.json` | New | 16 frontmatter files + ≥1 hook JSON |
| `docs/agents/copilot/README.md` | New | Narrative doc: platform gaps, layout, workarounds |
| `README.md` (root) | Modified | Add a reference to `docs/agents/copilot/README.md` in the relevant section |
| `src/ai_harness/resources/agent-clis/copilot-cli/agents/jd-*.md`, `agents/review-*.md` | New | Extracted JD + reviewer prompts (previously inline in `opencode.json`) |
| `src/ai_harness/resources/prompts/sdd/*.md` | Modified | 9 files generic-ified: skill paths expanded, "OpenCode's `task`" → "the platform's `task`" |
| `src/ai_harness/artifacts/installers/copilot.py` | Modified | Compose-at-install for agents, install hooks, install skills |
| `src/ai_harness/artifacts/catalog.py` | Modified (optional) | Add `.copilot/skills` to `SKILLS_TARGET_DIRS` if needed |
| `e2e/test_copilot_cli_lifecycle.py` | New | Fresh install + reinstall + uninstall + 30k limit + frontmatter checks |
| `e2e/tasks.py` | Modified | New `copilot_cli_lifecycle` invoke task |
| `tasks.py` (root) | Modified | Expose `copilot_cli_lifecycle` to the root collection |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Compose-at-install is new logic vs pure-copy loops | Med | TDD unit + e2e; isolate compose helper; verify deterministic output for backup content-matching |
| Prompt generic-ification may subtly shift wording other adapters rely on | Low | Additive changes only — append copilot-cli paths, never remove existing paths; replace OpenCode name with neutral phrase; tests cover install of opencode + claude |
| Implementation is LARGE; 800-line review budget enforced (precedent was scope-cut) | High | FLAG for `tasks.md` slicing — do NOT slice here, but `sdd-tasks` should group work into shippable slices |
| Hooks are new infrastructure (no copilot-cli equivalent in the repo yet) | Med | TDD: assert at least one `preToolUse` matcher for `task` tool with non-empty allowlist; assert fail-closed behavior |
| All 16 agents visible in `/agent` picker (no `hidden` flag) | Low | Document in adapter README; consistent naming convention |
| No declarative task allowlist (delegation is opportunistic) | Med | Hooks enforce the allowlist at `preToolUse`; orchestrator prompt also reinforces it |

## Rollback Plan

1. `git rm -r src/ai_harness/resources/agent-clis/copilot-cli/`
2. `git rm -r docs/agents/copilot/`
3. `git checkout HEAD -- src/ai_harness/artifacts/installers/copilot.py src/ai_harness/artifacts/catalog.py src/ai_harness/resources/prompts/sdd/*.md README.md`
4. `git rm e2e/test_copilot_cli_lifecycle.py` and revert the e2e/root `tasks.py` wiring
5. The next `ai-harness uninstall` (for users who installed the new adapter) restores the prior state from `.ai-harness-backup`

OpenCode and Claude adapter wiring and behavior are untouched. Existing installed `~/.copilot/copilot-instructions.md` continues to be managed by the current `CopilotInstaller`.

## Dependencies

- Shared `prompts/sdd/*.md` (single source of truth) must stay stable as the embedded content.
- `src/ai_harness/artifacts/installer.py` (generic `FileArtifact`/`DirArtifact` + backup/restore) is the foundation for compose-at-install; no changes needed there.
- copilot-cli custom-agent prompt limit is 30,000 chars; verified all 9 prompts fit with frontmatter overhead.

## Success Criteria

- [ ] `ai-harness install` stages 16 `~/.copilot/agents/*.agent.md`, ≥1 `~/.copilot/hooks/*.json`, and `~/.copilot/skills/<name>/SKILL.md` for every shared skill.
- [ ] Every installed `*.agent.md` has valid YAML frontmatter (`name`, `description`, `tools`) and is ≤ 30,000 chars.
- [ ] `~/.copilot/hooks/sdd-pre-tool-use.json` exists, has `version: 1`, and contains a `preToolUse` matcher for the `task` tool with an allowlist of 15 subagent names.
- [ ] `ai-harness install` (re-run) preserves user-authored `*.agent.md` and overrides stale project files, with `.ai-harness-backup` created.
- [ ] `ai-harness uninstall` removes all installed copilot-cli files and restores `.ai-harness-backup` content.
- [ ] `uv run pytest` + `uv run inv copilot-cli-lifecycle` pass (TDD: tests were red first, then green).
- [ ] No OpenCode-only assets (`opencode.json`, `plugins/model-variants.ts`, `blocks/sdd-model-assignments.md`) duplicated into the copilot-cli adapter.
- [ ] `docs/agents/copilot/README.md` exists, documents the platform gaps, and is referenced from the root `README.md`.

## Open Questions for the User

These three should be resolved during `sdd-design` (do not block `sdd-spec`):

1. **Hook allowlist exact contents.** Should the orchestrator's `task` allowlist match the opencode one (15 subagent names, omitting the dead `sdd-init`/`sdd-onboard` entries), or include the dead entries for forward compatibility?
2. **`*.agent.md` frontmatter schema.** Should we set `target: copilot-cli` to scope the agents to copilot-cli (avoiding leakage into VS Code/JetBrains when the same project is opened), or omit it for broader IDE coverage?
3. **Extracted JD/reviewer prompt location.** Should the JD and reviewer prompt bodies (currently inline in `opencode.json`) live as small markdown files under `agent-clis/copilot-cli/agents/jd-*.md` and `review-*.md` (proposal recommendation), or as a JSON map inside the adapter's `manifest.json`?

Defaults (proposed if the user does not answer): (1) omit dead entries, (2) omit `target`, (3) small markdown files under the adapter.
