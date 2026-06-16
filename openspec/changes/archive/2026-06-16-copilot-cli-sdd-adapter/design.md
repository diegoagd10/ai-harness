# Design: GitHub Copilot CLI SDD Adapter

## Architecture overview

```
ai-harness install
  │
  ├── OpencodeInstaller ─── FileArtifact/DirArtifact ─── ~/.config/opencode/
  ├── ClaudeInstaller ───── FileArtifact/DirArtifact/   ~/.claude/
  │                          ComposedFileArtifact
  └── CopilotInstaller ──── FileArtifact/DirArtifact/   ~/.copilot/
                             ComposedFileArtifact
```

`CopilotInstaller` reuses the generic installer foundation (`installer.py`) unchanged. New behavior lives entirely in `_build_manifest`: it composes 16 agents via `ComposedFileArtifact`, copies hooks as plain `FileArtifact`s, and installs skills via `DirArtifact`.

## Source adapter layout

```
agent-clis/copilot-cli/
├── README.md                             # platform gaps narrative
├── agents/
│   ├── sdd-orchestrator.md               # frontmatter only (with closing ---)
│   ├── sdd-{explore,propose,spec,design,tasks,apply,verify,archive}.md  (8)
│   ├── jd-{fix-agent,judge-a,judge-b}.md  (3)  frontmatter + inline body
│   └── review-{risk,readability,reliability,resilience}.md  (4)  frontmatter + inline body
└── hooks/
    └── sdd-pre-tool-use.json             # fail-closed tool allowlist + path deny
```

**Decision**: Follow the Claude adapter pattern. The 9 SDD phase + orchestrator source files are frontmatter-only (with closing `---`); bodies come from `prompts/sdd/` via `ComposedFileArtifact`. The 7 JD/reviewer agents are self-contained: frontmatter + body inline in the `.md` file, installed verbatim via `FileArtifact`. This mirrors the Claude adapter's split (8 composed + 7 verbatim) and makes each adapter self-contained for its JD/reviewer definitions.

## Composition strategy

`ComposedFileArtifact` (already defined in `feat/claude-installer-composition`, pending merge) concatenates `frontmatter + "\n---\n" + body`. The copilot-cli SDD phase frontmatter source files contain YAML with opening AND closing `---` (matching the Claude pattern). The join adds the second `---` separator; `ComposedFileArtifact` handles the delimiter correctly when a closing `---` is already present in the source.

The 7 JD/reviewer agents are NOT composed — they are `FileArtifact`s copied verbatim. Their `.md` files contain frontmatter + closing `---` + inline body (matching the Claude inline agent format exactly).

- **Phase agents** (8) + orchestrator (1): `ComposedFileArtifact` — frontmatter_source = `agents/sdd-<phase>.md`, body_source = `prompts/sdd/<phase>.md`
- **JD agents** (3): `FileArtifact` — source = `agents/jd-*.md` (frontmatter + inline body)
- **Reviewer agents** (4): `FileArtifact` — source = `agents/review-*.md` (frontmatter + inline body)

Determinism: same file content + same join → identical bytes. Backup/restore content-matching works unmodified.

## Frontmatter design

All 16 agents: `name`, `description`, `tools`. Omit `target` (broader IDE coverage). Omit `model` (copilot-cli ignores per-agent model).

Tool maps: `read` → `view`, `write` → `create`, `bash`/`edit`/`glob`/`grep`/`task` stay. Phase agents get write tools; judges get `read`/`view`/`bash` (read-only); reviewers same as judges.

## Hook JSON design

`preToolUse` matchers for `task`: allowlist of 15 subagent names (omit dead `sdd-init`/`sdd-onboard`), fail-closed `deny` default.

`preToolUse` matchers for `bash`/`view`/`create`/`edit`: deny writes to sensitive paths mirroring opencode external_directory: `~/.ssh/**`, `~/.aws/**`, `~/.gnupg/**`, `~/.zshrc`, `~/.bashrc`, `~/.bash_history`, `~/.zsh_history`, `~/.netrc`, `~/.config/gh/**`, `~/.docker/config.json`, `/tmp/**`, `/etc/**`, `/proc/**`, `/sys/**`, `/var/**`.

## Skills and instructions wiring

- `AGENTS.md` → `~/.copilot/copilot-instructions.md`: unchanged.
- `skills/` → `~/.copilot/skills/`: new `DirArtifact`.
- **Decision**: Add `.copilot/skills` to `SKILLS_TARGET_DIRS`. Rationale: catalog-level visibility enables consistent e2e assertions and future CLI-agnostic features (like `ai-harness skills list`). Cost is one tuple entry.

## Prompt generic-ification

Two changes across 9 files:

1. `sdd-orchestrator.md` lines 7 and 252: `"OpenCode's native \`task\` tool"` → `"the platform's native \`task\` tool"`.
2. All 8 phase prompts (explore through archive): expand skill-path block from 3 paths to 6, adding `{project-root}/.agents/skills/`, `{project-root}/.claude/skills/`, `{project-root}/.copilot/skills/`. `sdd-verify.md` line 50 inline list expanded identically.

Additive only — no existing path removed. OpenCode and Claude e2e tests must continue passing.

## Architecture Decision Records

**ADR-001**: Compose-at-install (chosen) over pre-composed files. Keeps prompts as single source of truth; avoids drift between adapter copies.

**ADR-002**: Reuse `ComposedFileArtifact` (chosen) over new abstraction. Already merged in `claude-installer-composition`; battle-tested with Claude adapter.

**ADR-003**: JD/reviewer bodies inline in copilot-cli `agents/*.md` (chosen) over shared `prompts/sdd/` body files. Follows the Claude adapter's mixed pattern: 9 composed SDD phase agents (bodies from shared `prompts/sdd/`) + 7 verbatim inline agents (self-contained). Each adapter (opencode, claude, copilot-cli) is now self-contained for its JD/reviewer definitions — no shared body files to drift. The 9 large SDD phase bodies remain in shared `prompts/sdd/` as canonical sources.

**ADR-004**: Hook allowlist omits dead `sdd-init`/`sdd-onboard` (chosen). These run inline in the orchestrator; never delegated.

**ADR-005**: Omit `target` field (chosen). Broader IDE coverage preferred over copilot-cli-only scoping.

**ADR-006**: Add `.copilot/skills` to `SKILLS_TARGET_DIRS` (chosen). Enables consistent catalog-level assertions.

**ADR-007**: Prompt generic-ification is additive only (chosen). Zero risk of breaking opencode/claude adapters.

## Risks

- copilot-cli hook JSON schema may differ from designed format (mitigation: e2e test validates installed JSON).
- Implementation size (~800 lines); task slicing in `sdd-tasks` is critical.
- `ComposedFileArtifact` is in an unmerged branch; design assumes merge before apply.
- The Phase 2a Option B approach (shared `prompts/sdd/` body files for JD/reviewer agents) was reverted in a Claude-pattern structural refactor (Phase 2a-bis). The user's preferred approach — mirroring the Claude adapter's mixed composed+inline pattern — is now in effect. The 7 JD/reviewer bodies are inline in `agent-clis/copilot-cli/agents/*.md`; opencode.json keeps its original inline bodies.

## Rollback

Remove new adapter directory, revert `CopilotInstaller` wiring, revert prompt line edits. Users who installed restore via existing `.ai-harness-backup` mechanism on next uninstall.
