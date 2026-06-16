# GitHub Copilot CLI — SDD Agent Adapter

Installs a 16-agent SDD (Spec-Driven Development) graph under `~/.copilot/`
via `ai-harness install`. The adapter is staged under the project's
`agent-clis/copilot-cli/` resource tree.

## What gets installed

| Target path | Content | Install mechanism |
|---|---|---|
| `~/.copilot/agents/*.agent.md` | 16 composed agent files (frontmatter + prompt body) | `ComposedFileArtifact` |
| `~/.copilot/hooks/sdd-pre-tool-use.json` | Tool-use access-control hook | `FileArtifact` |
| `~/.copilot/skills/` | Shared skill definitions | `DirArtifact` |
| `~/.copilot/copilot-instructions.md` | Global agent instructions | `FileArtifact` |

Backup copies are stored under `~/.ai-harness-backup/` on every content
change and restored on uninstall. The installer compares installed content
against source deterministically — only modified files are replaced.

## Agent layout (16 agents)

1. **Orchestrator** — `sdd-orchestrator`: coordinates the graph, never
   does implementation inline.
2. **Phase agents** (8) — `sdd-explore`, `sdd-propose`, `sdd-spec`,
   `sdd-design`, `sdd-tasks`, `sdd-apply`, `sdd-verify`, `sdd-archive`.
   Each owns one SDD workflow stage.
3. **Judgment-day agents** (3) — `jd-fix-agent`, `jd-judge-a`,
   `jd-judge-b`. Adversarial review protocol: two blind judges find
   problems, one fix agent applies surgeon-level corrections.
4. **Reviewer agents** (4) — `review-risk`, `review-readability`,
   `review-reliability`, `review-resilience`. Read-only specialized
   reviewers covering security, clarity, testing, and operations.

All 16 agents share the same prompt body sources (under the shared
`prompts/sdd/` tree) composed at install time with Copilot CLI-specific
frontmatter. The orchestrator delegates to the 15 subagents; subagents
never delegate further.

## Access control (hooks)

Copilot CLI does not support declarative per-agent permission declarations
(the `permission.*` fields available in OpenCode). Instead, this adapter
ships a pre-tool-use hook (`sdd-pre-tool-use.json`) that enforces:

- **Task delegation**: exactly 15 subagent names are allowlisted for the
  `task` tool. Any other name is denied. The orchestrator is the primary
  agent and is never delegated to.
- **Path deny**: `bash`, `view`, `create`, and `edit` tools are prevented
  from operating on sensitive paths mirroring the OpenCode
  `external_directory` deny list (`~/.ssh`, `~/.aws`, `/etc`, `/proc`,
  etc.).

The hook is fail-closed: tool invocations not matching an explicit allow
rule are denied by default.

## Platform gaps

### Per-agent `model`

Copilot CLI ignores per-agent model declarations. Users switch models
globally via the `/model` slash command or equivalent. The adapter
omits `model` from frontmatter; all agents inherit the current session
model.

### `hidden` flag

Copilot CLI has no `hidden` agent flag. All 16 agents appear in the
`/agent` picker. The naming convention (`sdd-*`, `jd-*`, `review-*`)
groups them for discoverability.

### Slash commands

Copilot CLI does not support custom slash commands. The orchestrator
prompt body includes natural-language trigger instructions so users can
invoke SDD workflows with phrases like "start explore for feature X"
instead of formal slash-command syntax.

### Per-agent character budget

Copilot CLI enforces a 30,000-character hard limit per agent file.
The `ComposedFileArtifact` installer validates this budget at install
time and refuses to write oversized agents.

## Composition pattern

Agent files are not pre-written in the adapter. Each agent is built at
install time by `ComposedFileArtifact`:

1. **Frontmatter source**: a YAML snippet (`---` + `name`, `description`,
   `tools`) from the adapter directory. No body text.
2. **Body source**: the prompt instructions from the shared `prompts/sdd/`
   tree (same source used by the OpenCode and Claude adapters).
3. **Join**: frontmatter + `\n---\n` + body → valid `.agent.md` file.

This keeps the prompt body as the single source of truth across all three
CLI adapters and eliminates drift between adapter copies.

## Adapter source

The adapter is staged under `src/ai_harness/resources/agent-clis/copilot-cli/`.
Installation is handled by `CopilotInstaller` which extends the generic
artifact installer foundation (`installer.py`).
