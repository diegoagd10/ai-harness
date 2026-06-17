# Exploration: refactor agent-clis installer architecture

## Context

The user wants to stop storing provider-specific resource files under `src/ai_harness/resources/agent-clis/` and instead keep a single source of truth under `prompts/` (and `skills/`). Each provider installer (OpenCode, Claude Code, Copilot CLI) should know its own syntax and build its config artifact in memory, then write it to the correct target path. The concrete pain point is `jd-judge-a.md`, whose prompt body is repeated in `claude/agents/`, `copilot-cli/agents/`, and as an inline string in `opencode/opencode.json`. This must be a pure refactor: end-user install experience and e2e behavior stay unchanged; e2e tests must not be modified.

## Current state

### Resource tree (`src/ai_harness/resources/agent-clis/`)

```text
agent-clis/
├── claude/
│   ├── agents/
│   │   ├── jd-fix-agent.md          # frontmatter + inline body
│   │   ├── jd-judge-a.md            # frontmatter + inline body  ← duplicated body
│   │   ├── jd-judge-b.md            # frontmatter + inline body
│   │   ├── review-readability.md    # frontmatter + inline body  ← duplicated body
│   │   ├── review-reliability.md    # frontmatter + inline body
│   │   ├── review-resilience.md     # frontmatter + inline body
│   │   ├── review-risk.md           # frontmatter + inline body
│   │   ├── sdd-apply.md             # frontmatter only
│   │   ├── sdd-archive.md           # frontmatter only
│   │   ├── sdd-design.md            # frontmatter only
│   │   ├── sdd-explore.md           # frontmatter only
│   │   ├── sdd-propose.md           # frontmatter only
│   │   ├── sdd-spec.md              # frontmatter only
│   │   ├── sdd-tasks.md             # frontmatter only
│   │   └── sdd-verify.md            # frontmatter only
│   └── sdd-orchestrator/
│       └── SKILL.md                 # frontmatter + body (Claude "Agent" tool variant)
├── copilot-cli/
│   ├── agents/
│   │   ├── jd-fix-agent.md          # frontmatter + inline body  ← body identical to claude
│   │   ├── jd-judge-a.md            # frontmatter + inline body  ← body identical to claude
│   │   ├── jd-judge-b.md            # frontmatter + inline body
│   │   ├── review-*.md              # frontmatter + inline body  ← bodies identical to claude
│   │   ├── sdd-*.md                 # frontmatter only
│   │   └── sdd-orchestrator.md      # frontmatter only
│   └── hooks/
│       └── sdd-pre-tool-use.json    # Copilot-specific policy JSON
└── opencode/
    ├── blocks/
    │   └── sdd-model-assignments.md # not installed today
    ├── plugins/
    │   ├── model-variants.ts        # not installed today
    │   └── model-variants.test.ts   # not installed today
    └── opencode.json                # JSON config with inline prompts for jd/review agents
```

### Duplication table

| Logical prompt | Current locations | Provider-specific wrapper |
|---|---|---|
| `sdd-explore` | `claude/agents/sdd-explore.md` (frontmatter), `copilot-cli/agents/sdd-explore.md` (frontmatter), `opencode.json` (`agent.sdd-explore`) | tools list, model key |
| `sdd-propose` | same pattern | tools list, model key |
| `sdd-spec` | same pattern | tools list, model key |
| `sdd-design` | same pattern | tools list, model key |
| `sdd-tasks` | same pattern | tools list, model key |
| `sdd-apply` | same pattern | tools list, model key |
| `sdd-verify` | same pattern | tools list, model key |
| `sdd-archive` | same pattern | tools list, model key |
| `sdd-orchestrator` | `claude/sdd-orchestrator/SKILL.md`, `copilot-cli/agents/sdd-orchestrator.md` + `prompts/sdd/sdd-orchestrator.md`, `opencode.json` | skill vs agent, `Agent` vs `task` tool |
| `jd-fix-agent` | `claude/agents/jd-fix-agent.md`, `copilot-cli/agents/jd-fix-agent.md`, `opencode.json` inline | tools list, model key |
| `jd-judge-a` | `claude/agents/jd-judge-a.md`, `copilot-cli/agents/jd-judge-a.md`, `opencode.json` inline | tools list, model key |
| `jd-judge-b` | `claude/agents/jd-judge-b.md`, `copilot-cli/agents/jd-judge-b.md`, `opencode.json` inline | tools list, model key |
| `review-risk` | `claude/agents/review-risk.md`, `copilot-cli/agents/review-risk.md`, `opencode.json` inline | tools list, model key |
| `review-readability` | `claude/agents/review-readability.md`, `copilot-cli/agents/review-readability.md`, `opencode.json` inline | tools list, model key |
| `review-reliability` | `claude/agents/review-reliability.md`, `copilot-cli/agents/review-reliability.md`, `opencode.json` inline | tools list, model key |
| `review-resilience` | `claude/agents/review-resilience.md`, `copilot-cli/agents/review-resilience.md`, `opencode.json` inline | tools list, model key |

Observations:
- The **bodies** of the seven inline agents (`jd-*`, `review-*`) are byte-identical between Claude and Copilot; only the YAML frontmatter differs.
- The eight SDD phase agents currently carry only frontmatter in both provider trees; their bodies already live in `prompts/sdd/*.md`.
- The orchestrator exists in two body variants: a Claude "Agent tool" variant (`claude/sdd-orchestrator/SKILL.md`) and a Copilot/OpenCode "task tool" variant (`prompts/sdd/sdd-orchestrator.md`).
- OpenCode already references `prompts/sdd/*.md` for phase agents via `{file:{{HOME}}/.config/opencode/prompts/sdd/...}` placeholders, but still embeds the seven inline agent prompts as strings.

## Installer flow

### CLI → installer dispatch

1. `ai-harness install --all` or `ai-harness install` enters `src/ai_harness/commands/artifacts/install.py::install()`.
2. `install()` creates an `ArtifactCatalog(RESOURCES_DIR)` and iterates selected agent IDs.
3. `src/ai_harness/artifacts/registry.py::get_installer()` maps IDs to classes: `opencode` → `OpencodeInstaller`, `claude` → `ClaudeInstaller`, `copilot` → `CopilotInstaller`.
4. Each installer builds an `ArtifactManifest` and calls the generic `ai_harness.artifacts.installer.install()` / `uninstall()` functions, which perform backup/restore/conflict rotation.

### Per-provider staging

- **OpencodeInstaller** (`src/ai_harness/artifacts/installers/opencode.py`)
  - Copies `resources/AGENTS.md` → `~/.config/opencode/AGENTS.md` and `~/.agents/AGENTS.md`.
  - Copies `resources/agent-clis/opencode/opencode.json` → `~/.config/opencode/opencode.json` with `{{HOME}}` → `$HOME` substitution.
  - Copies `resources/prompts/sdd/*.md` → `~/.config/opencode/prompts/sdd/*.md`.
  - Copies `resources/skills/` → `~/.agents/skills/`.

- **ClaudeInstaller** (`src/ai_harness/artifacts/installers/claude.py`)
  - Copies `resources/AGENTS.md` → `~/.claude/CLAUDE.md`.
  - Composes `resources/agent-clis/claude/agents/<phase>.md` + `resources/prompts/sdd/<phase>.md` → `~/.claude/agents/<phase>.md` for eight SDD phases.
  - Copies seven inline agents verbatim from `resources/agent-clis/claude/agents/` → `~/.claude/agents/`.
  - Copies `resources/skills/` → `~/.claude/skills/`.
  - Copies `resources/agent-clis/claude/sdd-orchestrator/` → `~/.claude/skills/sdd-orchestrator/`.
  - Calls `install_permissions()` to merge rules into `~/.claude/settings.json`.

- **CopilotInstaller** (`src/ai_harness/artifacts/installers/copilot.py`)
  - Copies `resources/AGENTS.md` → `~/.copilot/copilot-instructions.md`.
  - Composes `resources/agent-clis/copilot-cli/agents/<phase>.md` + `resources/prompts/sdd/<phase>.md` → `~/.copilot/agents/<phase>.md` for nine names (including orchestrator).
  - Copies seven inline agents verbatim from `resources/agent-clis/copilot-cli/agents/` → `~/.copilot/agents/`.
  - Copies `resources/agent-clis/copilot-cli/hooks/sdd-pre-tool-use.json` → `~/.copilot/hooks/sdd-pre-tool-use.json`.
  - Copies `resources/skills/` → `~/.copilot/skills/`.
  - Validates frontmatter and a 30,000-character composed budget.

### Generic installer

`src/ai_harness/artifacts/installer.py` owns backup, conflict rotation, template substitution, and uninstall restore. It operates on `FileArtifact`, `ComposedFileArtifact`, and `DirArtifact` descriptors produced by each installer.

## Provider syntax quirks

### OpenCode (`opencode.json`)

- Target path: `~/.config/opencode/opencode.json`.
- Single JSON object with top-level `permission`, `agent`, and `share` keys.
- Agent entries need `description`, `mode` (`primary`/`subagent`), `hidden` (for subagents), `prompt`, `tools`, optional `model`, and optional `permission` overrides.
- Prompts for SDD phase agents use `{file:{{HOME}}/.config/opencode/prompts/sdd/<phase>.md}` placeholders; the installer must substitute `{{HOME}}` with the real HOME path.
- The seven inline agents currently embed their prompt text directly in `opencode.json`.
- The `sdd-orchestrator` agent has a `permission.task` allowlist enumerating every delegable subagent name.

### Claude Code (agent files + `settings.json`)

- Target paths:
  - `~/.claude/CLAUDE.md` for global instructions.
  - `~/.claude/agents/<name>.md` for subagents.
  - `~/.claude/skills/sdd-orchestrator/SKILL.md` for the orchestrator skill.
- Agent files are Markdown with YAML frontmatter delimited by `---`.
- Required frontmatter keys: `name`, `description`, `tools`. Optional: `model`.
- Tools are Claude-native names: `Read`, `Edit`, `Write`, `Bash`, `Agent`, `Glob`, `Grep`, etc.
- Phase agents are composed at install time: frontmatter file + `prompts/sdd/<phase>.md` body joined by `\n---\n`.
- Inline agents are copied verbatim (frontmatter + body in one file).
- `install_permissions()` maps declared tools to `settings.json` `permissions.allow` rules (`Glob`/`Grep` → `Read`) and tracks managed rules with `~/.claude/.ai-harness-managed-allow.json`.

### Copilot CLI (agent files + hook JSON)

- Target paths:
  - `~/.copilot/copilot-instructions.md` for global instructions.
  - `~/.copilot/agents/<name>.md` for subagents.
  - `~/.copilot/hooks/sdd-pre-tool-use.json` for tool policy.
- Agent files are Markdown with YAML frontmatter; the frontmatter parser in `CopilotInstaller._validate_agent_frontmatter()` requires `name`, `description`, `tools`.
- Tools are Copilot-native names: `View`, `Edit`, `Create`, `Bash`, `Glob`, `Grep`, `Task`.
- Phase agents (including orchestrator) are composed at install time from frontmatter + `prompts/sdd/*.md` body.
- Inline agents are copied verbatim.
- Hook JSON declares `version: 1`, `preToolUse` matchers. The `task` matcher is fail-closed (`default: deny`) with a 15-name allowlist. Four write-capable tools (`bash`, `view`, `create`, `edit`) carry `deny.paths` lists that mirror OpenCode's `external_directory` deny list.
- `CopilotInstaller` enforces a 30,000-character budget on composed agents.

## E2E coverage surface

The e2e suite is the immovable safety net. Relevant files:

- `e2e/test_harness_lifecycle.py`
  - `OPENCODE_JSON_SRC`: reads `resources/agent-clis/opencode/opencode.json` as the expected source and compares it to `~/.config/opencode/opencode.json` after `{{HOME}}` substitution.
  - `CLAUDE_AGENTS_SRC`: reads `resources/agent-clis/claude/agents/` and composes expected files for `~/.claude/agents/`.
  - `SDD_PROMPTS_SRC`: reads `resources/prompts/sdd/` for composed bodies.
  - `CLAUDE_ORCHESTRATOR_SRC`: asserts `~/.claude/skills/sdd-orchestrator/SKILL.md` exists.
  - Asserts 15 `.md` files under `~/.claude/agents/`.
  - Asserts `~/.claude/settings.json` permissions, marker, and backup.
  - Asserts skills copied to `.agents/skills/` and `.claude/skills/`.
  - Asserts SDD prompts copied to `.config/opencode/prompts/sdd/`.
  - Asserts `AGENTS.md` targets (`.agents/AGENTS.md`, `.claude/CLAUDE.md`, `.copilot/copilot-instructions.md`).

- `e2e/test_copilot_cli_lifecycle.py`
  - `COPILOT_AGENTS_SRC`: reads `resources/agent-clis/copilot-cli/agents/` and asserts all 16 expected `.md` files exist under `~/.copilot/agents/`.
  - `COPILOT_HOOKS_SRC`: reads `resources/agent-clis/copilot-cli/hooks/sdd-pre-tool-use.json` and validates version, `preToolUse` structure, `task` allowlist, and deny paths.
  - Asserts `~/.copilot/copilot-instructions.md`, `~/.copilot/hooks/sdd-pre-tool-use.json`, and `~/.copilot/skills/`.
  - Asserts every installed agent has valid YAML frontmatter with `name`/`description`/`tools`.
  - Asserts every installed agent is ≤ 30,000 characters.

- `e2e/test_wizard_lifecycle.py`
  - State-file semantics only; does not inspect provider artifacts.

- `e2e/test_sdd_lifecycle.py`
  - SDD command flow only; does not inspect provider artifacts.

**Important**: these tests read source files from hard-coded paths under `src/ai_harness/resources/agent-clis/`. The refactor must either keep those paths populated (e.g., as generated artifacts or shims) or update non-e2e tests only; the e2e files themselves must remain untouched.

## Existing OpenSpec constraints

- `claude-permissions/spec.md`
  - Tool union from staged sub-agents + orchestrator `SKILL.md` must map to `Bash`, `Read`, `Edit`, `Write`, `Agent` rules.
  - `Glob`/`Grep` must satisfy a single `Read` rule.
  - Merge must be idempotent; existing user entries preserved.
  - `CLAUDE_CONFIG_DIR` overrides default `~/.claude/settings.json`.
  - Backup before modification; do not overwrite existing backup.
  - Marker file `~/.claude/.ai-harness-managed-allow.json` records managed rules; uninstall removes only those, with 5-name fallback if marker is missing/corrupt.

- `install-wizard/spec.md`
  - Fixed order: OpenCode, Claude Code, Copilot CLI.
  - Pre-select non-installed agents; all pre-selected on fresh install.
  - `j`/`k`, arrows, space, enter, esc behavior.
  - Marker-only selection styling.
  - Empty selection and cancellation terminal states.

- `uninstall-wizard/spec.md`
  - Show only installed agents; nothing pre-selected.
  - All-or-nothing state update; delete state file on last uninstall.
  - Same UI behavior as install wizard.

None of these specs prescribe the on-disk resource layout, but the `claude-permissions` spec requires the Claude installer to locate frontmatter from staged sub-agents and the orchestrator `SKILL.md` to compute the tool union.

## Shared source candidates

Content that can become provider-agnostic source:

| Source | Current location(s) | Notes |
|---|---|---|
| SDD phase bodies (8) | `prompts/sdd/sdd-*.md` | Already shared; keep. |
| Orchestrator body (task variant) | `prompts/sdd/sdd-orchestrator.md` | Used by Copilot (composed) and OpenCode (`{file:...}`). |
| Orchestrator body (Agent variant) | `claude/sdd-orchestrator/SKILL.md` | Claude-specific because it references the `Agent` tool. Could be a templated variant of the same source or a separate file. |
| JD/reviewer bodies (7) | Inline in `claude/agents/*.md` and `copilot-cli/agents/*.md` | Should move to `prompts/jd-*.md` and `prompts/review-*.md`. |
| AGENTS.md | `resources/AGENTS.md` | Already shared; copied verbatim to all providers. |
| Skills | `resources/skills/` | Already shared; copied verbatim. |

Provider-specific glue that must stay per-installer:

- Frontmatter (tool names, model keys).
- `opencode.json` schema construction and `{file:...}` path generation.
- Copilot hook JSON generation (including the 15-name task allowlist and deny paths).
- Claude `settings.json` permissions merge.
- File target paths (`.claude/agents/`, `.copilot/agents/`, `.config/opencode/...`).

## Open questions for proposal

1. **Where do the shared prompt bodies live?**
   - Option A: flat under `prompts/` (e.g., `prompts/jd-judge-a.md`, `prompts/sdd-explore.md`).
   - Option B: grouped by namespace (`prompts/sdd/*.md` for phases, `prompts/jd/*.md`, `prompts/review/*.md`).
   - The existing `prompts/sdd/` convention should probably be preserved or migrated consistently.

2. **How do we represent per-provider frontmatter/metadata?**
   - Option A: a small metadata file (YAML/JSON) per provider that lists agents, descriptions, models, and tools; installers read it and compose files.
   - Option B: keep minimal frontmatter templates per provider (e.g., `installers/data/claude-frontmatter.yaml`) and generate files from shared bodies.
   - Option C: embed the metadata directly in each installer class as structured data.

3. **What is the source of truth for the orchestrator body?**
   - There are already two variants (Agent-tool for Claude, task-tool for Copilot/OpenCode). Do we keep two source files with shared sections, or introduce lightweight templating (`{{DELEGATION_TOOL}}`) so one source produces both?

4. **Does `opencode.json` become generated in memory or remain a static template?**
   - If generated, the installer can build agent entries from shared metadata and replace inline prompt strings with `{file:...}` references (or keep them inline if required).
   - If it stays a template, duplication remains for the inline agents unless the template is rendered from shared source.

5. **How do we satisfy e2e tests that read `agent-clis/<provider>/` source paths?**
   - Option A: keep generated/shim files at the old paths so e2e assertions continue to pass unchanged.
   - Option B: change the e2e source constants (not allowed by user constraint).
   - Option C: make the e2e tests read from the new canonical `prompts/` tree without editing them (not possible because constants are hard-coded).
   - The proposal must pick Option A or argue for an exception.

6. **What happens to the Copilot hook JSON and OpenCode `permission` blocks?**
   - They contain provider-specific policy (deny paths, task allowlist). Should these be generated from a shared policy description, or remain provider-specific code/data?

## Risks

- **E2E path coupling**: `e2e/test_harness_lifecycle.py` and `e2e/test_copilot_cli_lifecycle.py` import source paths from `src/ai_harness/resources/agent-clis/`. If those directories are removed, the e2e tests break unless shims remain. Since e2e tests must not be modified, this is the highest-risk constraint.
- **Byte-identical output**: The generic installer compares installed content to source-derived content for uninstall/backup decisions. Any change in how files are composed (e.g., trailing newlines, separator lines) can alter the expected bytes and break idempotency or uninstall-restore behavior.
- **Claude permissions mapping**: The permission logic relies on reading frontmatter from staged agent files. If frontmatter moves into generated in-memory structures, `install_permissions()` must still receive the same tool lists and orchestrator info.
- **Copilot frontmatter validation**: `CopilotInstaller` validates `name`/`description`/`tools` at manifest-build time. The refactor must preserve those validation semantics.
- **Copilot 30K budget**: The budget check depends on exact composed length. Moving bodies to shared source must not change the composed length unexpectedly.
- **OpenCode `{file:...}` substitution**: The `{{HOME}}` token is currently replaced only in `opencode.json`. If prompts move, any new `{file:...}` paths must also be substituted correctly.
- **Test imports**: `tests/test_install.py` and `tests/test_uninstall.py` import constants like `AGENTS_MD_SRC`, `OPENCODE_JSON_SRC`, etc., from `ai_harness.artifacts.catalog`. These constants may need to move or change, which is acceptable (unit tests are not e2e), but the change must be coordinated.
- **Static resource packaging**: `pyproject.toml` does not list `package-data`; verify that files under `src/ai_harness/resources/` are included by the build backend (uv_build) before and after layout changes.

## Recommendation

Proceed with a proposal that:

1. Keeps the existing `agent-clis/<provider>/` directories as **generated install inputs** (or lightweight shims) so e2e source-path constants keep working without touching e2e tests.
2. Introduces a canonical `prompts/` tree containing provider-agnostic bodies for all agents (phases, orchestrator variants, jd-*, review-*).
3. Moves provider-specific metadata (frontmatter fields, tool names, models, hook allowlists) into structured data inside each installer module or a small per-provider data file.
4. Generates `opencode.json` in memory from the same metadata + shared bodies, replacing the inline prompt strings with `{file:...}` references or rendered strings as needed.
5. Generates the Copilot hook JSON in memory from a shared policy description so deny paths and the task allowlist no longer live as raw JSON under `agent-clis/copilot-cli/hooks/`.

This preserves the end-user install surface, satisfies the no-e2e-touch constraint, and removes the duplicated prompt bodies.
