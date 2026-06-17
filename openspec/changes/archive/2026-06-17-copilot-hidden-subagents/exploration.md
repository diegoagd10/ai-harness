# Exploration: copilot-hidden-subagents

## Change context

The GitHub Copilot installer currently emits the same 16-agent SDD graph as the OpenCode and Claude installers, but it does not take advantage of the Copilot custom-agent `user-invocable` property. The goal is to make the Copilot installer produce first-class custom agents so that only `sdd-orchestrator` is selectable by the end user, while the 15 subagents (`sdd-*` phases, `jd-*`, `review-*`) are hidden from the user picker via `user-invocable: false`. The orchestrator must still be able to delegate to those hidden agents through the `agent` tool alias (`custom-agent`, `Task`). This mirrors the OpenCode `hidden: true` / Claude `Agent` permission model already in place for the other providers.

## Current state of the Copilot installer

- **Source file**: `src/ai_harness/artifacts/installers/copilot.py` (`CopilotInstaller` class, lines 247–357).
- **What it emits today**:
  - `AGENTS.md` → `~/.copilot/copilot-instructions.md` (`FileArtifact`, line 280–284).
  - 16 composed agent files under `~/.copilot/agents/{name}.md` (`ComposedFileArtifact`, lines 288–311). **Note the extension is `.md`, not the custom-agent canonical `.agent.md` documented by GitHub.**
  - Hook JSON → `~/.copilot/hooks/sdd-pre-tool-use.json` (`FileArtifact` sourced from a temp file, lines 314–324).
  - Skills → `~/.copilot/skills/` (`DirArtifact`, lines 328–335).
- **Metadata carried today**: `_METADATA` (lines 95–182) contains only `name`, `description`, and `tools` per agent. It omits `model`, `target`, `user-invocable`, and `disable-model-invocation`.
- **Tool naming**: the orchestrator lists `tools: ["Task", "Bash", "Edit", "View", "Create", "Glob", "Grep", "Read"]` (line 100). The other 15 agents also include `"Task"` (lines 105–181). Per the GitHub docs, `Task` is a compatible alias for the `agent` tool, so the orchestrator already has the delegation primitive.
- **What is missing relative to the Copilot custom agents spec**:
  - `user-invocable: false` on subagents.
  - `user-invocable: true` on the orchestrator (this is the default, but being explicit is safer).
  - `target: github-copilot` to scope the profiles to Copilot CLI / cloud agent (optional but recommended).
  - `disable-model-invocation: true` (formerly `infer: false`) to prevent Copilot cloud agent from auto-selecting subagents.
  - A clear allowlist model: the existing hook JSON gates `task` by name, but the orchestrator's own `tools` list is broad. The docs note that an empty `tools` list disables all tools; omitting or using `["*"]` enables all. The current metadata emits explicit tool lists.

## Current state of the agent catalog

The canonical 16-agent set is defined consistently across installers (see `agent-clis-installer/spec.md` lines 185–190 and `opencode.py` `AGENT_DEFINITIONS` lines 153–332):

| Agent id | Family | Copilot tools today (`copilot.py:95-182`) | OpenCode mode / hidden (`opencode.py:153-332`) | Claude model (`claude.py:69-173`) |
|---|---|---|---|---|
| `sdd-orchestrator` | SDD orchestrator | `Task, Bash, Edit, View, Create, Glob, Grep, Read` | `mode: primary`, `hidden: false` | `model: inherit` |
| `sdd-explore` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/kimi-k2.7-code` | `model: inherit` |
| `sdd-propose` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/deepseek-v4-pro` | `model: inherit` |
| `sdd-spec` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/deepseek-v4-pro` | `model: inherit` |
| `sdd-design` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/deepseek-v4-pro` | `model: inherit` |
| `sdd-tasks` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/deepseek-v4-pro` | `model: inherit` |
| `sdd-apply` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/deepseek-v4-pro` | `model: inherit` |
| `sdd-verify` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/kimi-k2.6` | `model: inherit` |
| `sdd-archive` | SDD phase | `Bash, Edit, View, Create, Glob, Grep, Read, Task` | `mode: subagent`, `hidden: true`, `model: opencode-go/deepseek-v4-flash` | `model: inherit` |
| `jd-fix-agent` | JD / judgment-day | `Bash, Edit, View, Create, Task` | `mode: subagent`, `hidden: true`, no model | `model: inherit` |
| `jd-judge-a` | JD / judgment-day | `View, Bash, Glob, Grep, Task` | `mode: subagent`, `hidden: true`, no model, `permission.edit: deny` | `model: opus` |
| `jd-judge-b` | JD / judgment-day | `View, Bash, Glob, Grep, Task` | `mode: subagent`, `hidden: true`, no model, `permission.edit: deny` | `model: opus` |
| `review-risk` | Reviewer (R1–R4) | `View, Bash, Glob, Grep, Task` | `mode: subagent`, `hidden: true`, no model, `permission.edit: deny` | `model: opus` |
| `review-readability` | Reviewer | `View, Bash, Glob, Grep, Task` | `mode: subagent`, `hidden: true`, no model, `permission.edit: deny` | `model: sonnet` |
| `review-reliability` | Reviewer | `View, Bash, Glob, Grep, Task` | `mode: subagent`, `hidden: true`, no model, `permission.edit: deny` | `model: sonnet` |
| `review-resilience` | Reviewer | `View, Bash, Glob, Grep, Task` | `mode: subagent`, `hidden: true`, no model, `permission.edit: deny` | `model: sonnet` |

**Per-provider metadata keys**:
- **OpenCode**: `description`, `mode`, `prompt`, `tools`, optional `hidden`, `model`, `permission`.
- **Claude frontmatter**: `name`, `description`, `tools`, `model`.
- **Copilot frontmatter today**: `name`, `description`, `tools` only.

The two orchestrator bodies are preserved per `agent-clis-installer/spec.md` lines 15 and 274–278:
- `prompts/sdd/sdd-orchestrator.md` — task/orchestrator body used by OpenCode and Copilot.
- `prompts/orchestrator/sdd-orchestrator-agent.md` — Agent-variant body used by Claude only.

## Gap analysis

| Concern | Claude today | OpenCode today | Copilot today | Copilot after this change |
|---|---|---|---|---|
| Per-agent markdown file | `~/.claude/agents/{name}.md` + orchestrator skill | `~/.config/opencode/opencode.json` points to `{file:...}` or inline | `~/.copilot/agents/{name}.md` | Should be `~/.copilot/agents/{name}.agent.md` per GitHub custom-agent convention |
| Frontmatter keys | `name`, `description`, `tools`, `model` | JSON keys `description`, `mode`, `tools`, `prompt`, optional `model`, `permission`, `hidden` | `name`, `description`, `tools` | Add `target`, `user-invocable`, `disable-model-invocation`; optionally `model` |
| User-invocability | Not declarative; all agents visible | `hidden: true` on 15 subagents, `hidden: false` on orchestrator | No flag; all 16 agents visible in `/agent` picker | `user-invocable: false` on 15 subagents, `true` on orchestrator |
| Agent-tool allowlist in orchestrator | `settings.json` `permissions.allow` includes `Agent` rule; orchestrator `tools` lists `Agent` | `permission.task` allowlist: `*` deny + 15 subagents allow | Hook JSON `task` matcher denies by default and allows 15 names | Keep hook allowlist; additionally the orchestrator's `tools` frontmatter must include `agent`/`Task` |
| Hook/permission allowlist | `settings.json` merge via `permissions.py` | `permission.task` in `opencode.json` | `sdd-pre-tool-use.json` `preToolUse.task` allowlist | Keep, possibly narrow to orchestrator-only delegation |
| Model pinning | Per-agent `model` (`inherit`, `opus`, `sonnet`) | Per-agent `model` pinned for 9 SDD agents | None (inherits session model) | Docs allow `model` key; proposal should decide whether to pin |
| Uninstall behavior | Removes managed agents + restores backups + removes managed `permissions.allow` rules | Removes managed files + restores backups | Removes managed files + restores backups (generic uninstall) | Same generic uninstall; no `permissions.py` equivalent needed |
| Idempotency | Byte-identical reinstall | Byte-identical reinstall | Byte-identical reinstall | Must remain byte-identical; frontmatter order must be deterministic |

**Key mismatch**: the current installer writes `~/.copilot/agents/{name}.md`, but GitHub's custom agents documentation describes files with the `.agent.md` extension. The file name (minus `.md` or `.agent.md`) is used for deduplication, so the extension matters for precedence and discoverability. The existing e2e comments refer to `*.agent.md` (`e2e/test_copilot_cli_lifecycle.py:78`, `:99`, `:111`) while the actual path constants do not enforce the extension. This needs resolution in the proposal.

## Design space

### Option A: emit one `*.agent.md` per agent with custom-agent frontmatter

Emit 16 files under `~/.copilot/agents/{name}.agent.md` with frontmatter that includes:

```yaml
---
name: sdd-explore
description: SDD Explore — explores the codebase ...
tools: [agent, bash, edit, view, create, search, read]
target: github-copilot
user-invocable: false
disable-model-invocation: true
---
```

The orchestrator gets `user-invocable: true` (explicit default) and `disable-model-invocation: true` so the cloud agent does not auto-pick it. The orchestrator's `tools` list includes `agent` (or its `Task` alias) so it can delegate; subagents also keep `agent` if they need to hand off (the current spec does not require subagents to delegate further, but the prompts may reference the ability).

- **Pros**:
  - Matches the GitHub custom-agent spec literally (`user-invocable: false` only has meaning when there is a custom-agent profile to hide).
  - Uses the canonical `.agent.md` extension and `target: github-copilot`.
  - Self-documenting frontmatter; IDE/Copilot CLI behavior is explicit.
  - Parallels OpenCode `hidden: true` and Claude `Agent` permission semantics.
- **Cons**:
  - Requires updating `metadata_to_frontmatter` or adding a Copilot-specific serializer to emit new keys (`target`, `user-invocable`, `disable-model-invocation`) without leaking them into Claude frontmatter.
  - May require renaming installed files from `.md` to `.agent.md`, which affects e2e assertions and backup/uninstall paths.
  - Tool aliases must be reconciled: Copilot docs list lowercase aliases (`agent`, `bash`, `edit`, `view`, `create`, `search`, `read`) while current metadata uses TitleCase (`Task`, `Bash`, `Edit`, etc.). The docs state aliases are case-insensitive, but consistency reduces surprise.
- **Effort**: Medium.

### Option B: keep current hook-driven approach and only tag the orchestrator

Leave the 15 subagents as plain `.md` files (not registered as custom agents) and only add a single `sdd-orchestrator.agent.md` with `user-invocable: true` and `disable-model-invocation: true`. Subagents are "hidden" by virtue of not being custom-agent files at all.

- **Pros**:
  - Minimal file-surface change.
  - No need to extend `metadata_to_frontmatter` with Copilot-only keys.
- **Cons**:
  - Violates the spirit of the GitHub docs: `user-invocable: false` is a property of a custom-agent profile. If subagents are not custom agents, the orchestrator cannot delegate to them via the `agent` tool alias.
  - Breaks parity with OpenCode/Claude, where subagents are real agents that are hidden.
  - The existing hook JSON allowlist becomes meaningless if the subagent names are not recognized custom agents.
- **Effort**: Low, but semantically wrong.

### Option C: hybrid — custom-agent files + hook allowlist

Emit 16 `.agent.md` files (Option A) but keep the existing `sdd-pre-tool-use.json` hook as a defense-in-depth layer. The hook gates the `task` tool to the 15 subagent names, while the frontmatter gates user pickability.

- **Pros**:
  - Defense in depth: frontmatter hides agents from users; hook enforces runtime delegation policy.
  - Keeps the existing deterministic hook JSON contract already tested in `tests/test_copilot_installer.py:190-223` and `e2e/test_copilot_cli_lifecycle.py:143-162`.
  - Aligns with the Copilot docs, which describe both custom-agent profiles and cloud-agent hooks.
- **Cons**:
  - Slightly larger manifest and two sources of truth for the allowlist (frontmatter + hook).
  - If the hook and frontmatter disagree, behavior is confusing; tests must keep them synchronized.
- **Effort**: Medium.

### Recommendation

**Option C** is recommended. The GitHub documentation is explicit that `user-invocable: false` controls whether a custom agent can be selected by a user, and that the `agent` tool alias (`custom-agent`, `Task`) allows one custom agent to invoke another. Therefore, subagents must exist as custom-agent files to be delegable; simply not emitting them (Option B) would remove the delegation target. Option A is also viable, but dropping the hook would discard an existing, tested runtime enforcement layer for zero practical benefit. Keeping the hook while adding the frontmatter flags (Option C) gives two complementary controls: frontmatter for UX visibility, hook for runtime tool policy.

## Open questions

1. **File extension and location**: Should installed Copilot agent files be renamed from `.copilot/agents/{name}.md` to `.copilot/agents/{name}.agent.md`? The GitHub docs use `.agent.md`; the current code and tests use `.md`. The e2e comments already assume `.agent.md` but the assertions do not enforce it.
2. **Hook fate**: Should `sdd-pre-tool-use.json` be kept, deprecated, or merged into the custom-agent frontmatter? Recommendation: keep it as defense-in-depth.
3. **Orchestrator variant**: Should the Copilot orchestrator body continue to come from `prompts/sdd/sdd-orchestrator.md` (task variant) or from `prompts/orchestrator/sdd-orchestrator-agent.md` (Agent variant)? Currently Copilot uses the task variant; since Copilot supports the `agent` tool alias, either could work, but changing it affects prompts and tests.
4. **Tool aliases**: Should Copilot metadata switch to lowercase aliases (`agent`, `bash`, `edit`, `view`, `create`, `search`, `read`) per the docs, or keep TitleCase? The docs say aliases are case-insensitive, but lowercase is the documented primary form.
5. **Model pinning**: Should Copilot agents pin per-agent models as OpenCode does? The docs allow a `model` key. If yes, what model identifiers are valid for Copilot? This is `UNKNOWN — needs verification by the proposal phase`.
6. **Target value**: Should every agent frontmatter include `target: github-copilot`, or should it be omitted so the agent is visible in both IDE and Copilot CLI? The change intent says "visible in Copilot CLI / cloud agent," so `target: github-copilot` seems appropriate.
7. **Uninstall contract**: The generic installer already removes managed files and restores backups. Does the Copilot installer need a marker file like Claude's `.ai-harness-managed-allow.json`? Probably not, because the manifest itself is the single source of truth for file removal.
8. **Frontmatter serializer extension**: Should `metadata_to_frontmatter` grow optional keys (`target`, `user-invocable`, `disable-model-invocation`), or should Copilot use a separate serializer? A separate serializer is safer to avoid leaking Copilot keys into Claude frontmatter.
9. **Subagent `agent` tool**: Should subagents keep `agent`/`Task` in their `tools` list? Current metadata includes it, but the SDD contract says subagents do not delegate further. Removing it would be a minor hardening measure.
10. **Test updates**: The e2e `test_copilot_cli_lifecycle.py` currently validates 16 `.md` files. It will need to validate `user-invocable` and `disable-model-invocation` frontmatter keys and possibly the `.agent.md` extension.

## Out of scope

- Adding MCP server configuration to Copilot agents.
- Adding Copilot cloud-agent secrets or organization-level agent configuration.
- Rewriting the OpenCode installer or changing its `hidden`/`permission.task` model.
- Changing Claude installer behavior (settings.json merge, backup, allowlist).
- Modifying the canonical prompt bodies under `resources/prompts/` except as required to support the Agent variant decision.
- Generalizing the frontmatter serializer beyond the three existing providers.

## References

- GitHub Copilot custom agents configuration reference: https://docs.github.com/en/copilot/reference/custom-agents-configuration
- `src/ai_harness/artifacts/installers/copilot.py` — current Copilot installer
- `src/ai_harness/artifacts/installers/opencode.py` — OpenCode `hidden`/`permission.task` model
- `src/ai_harness/artifacts/installers/claude.py` — Claude `Agent` permission model
- `src/ai_harness/artifacts/installers/frontmatter.py` — shared frontmatter serializer
- `src/ai_harness/artifacts/installers/permissions.py` — Claude settings.json merge/cleanup
- `openspec/specs/agent-clis-installer/spec.md` — canonical 16-agent catalog and build-from-code contract
- `openspec/specs/claude-permissions/spec.md` — Claude permissions merge/backup/uninstall contract
- `e2e/test_copilot_cli_lifecycle.py` — existing Copilot e2e assertions
- `tests/test_copilot_installer.py` — unit tests for hook JSON and composed agents
- `docs/agents/copilot/README.md` — current (slightly outdated) Copilot adapter docs noting "no `hidden` flag"
