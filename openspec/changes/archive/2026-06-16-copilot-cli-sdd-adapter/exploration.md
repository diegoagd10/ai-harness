## Exploration: GitHub Copilot CLI SDD adapter (`copilot-cli-sdd-adapter`)

### Goal

Add `src/ai_harness/resources/agent-clis/copilot-cli/` and extend `CopilotInstaller` so that `ai-harness install` writes the full SDD agent graph (1 orchestrator + 8 phase subagents + 3 judgment-day agents + 4 R1–R4 reviewers), hooks, global instructions, and skills under `~/.copilot/`. The target is parity with what the OpenCode adapter installs under `~/.config/opencode/`, mapped to GitHub Copilot CLI's `*.agent.md`, hook JSON, and skill conventions.

### Current state

- **Command entry point.** `src/ai_harness/main.py` registers artifact commands via `register_artifact_commands`. `src/ai_harness/commands/artifacts/install.py` and `uninstall.py` loop over `OpencodeInstaller`, `ClaudeInstaller`, and `CopilotInstaller`.
- **Generic installer.** `src/ai_harness/artifacts/installer.py` owns backup/restore, template substitution, and `FileArtifact`/`DirArtifact` I/O. It is CLI-agnostic and deterministic: uninstall removes a file only when its installed content matches the prepared source content, then restores from `.ai-harness-backup`.
- **Catalog.** `src/ai_harness/artifacts/catalog.py` discovers `resources/AGENTS.md`, `resources/skills/`, and CLI-specific resources. `AGENTS_MD_TARGETS` already includes `.copilot/copilot-instructions.md`; `SKILLS_TARGET_DIRS` currently lists `.agents/skills` and `.claude/skills` only.
- **OpenCode adapter (parity target).** `src/ai_harness/resources/agent-clis/opencode/opencode.json` defines the agent graph, `blocks/sdd-model-assignments.md` supplies a model-reading prompt block, and `plugins/model-variants.ts` is an OpenCode-only runtime plugin. The adapter has **no** `agents/`, `hooks/`, `instructions/`, or `skills/` directories of its own — agents live in JSON, instructions come from the shared `resources/AGENTS.md`, and skills come from the shared `resources/skills/`.
- **Claude adapter (reference shape).** `src/ai_harness/resources/agent-clis/claude/agents/*.md` and `sdd-orchestrator/SKILL.md` are plain files. `ClaudeInstaller` already copies them, so this is "files only, no code."
- **Copilot adapter today.** `src/ai_harness/artifacts/installers/copilot.py` only installs `resources/AGENTS.md` → `~/.copilot/copilot-instructions.md`. It has no agent, hook, or skill wiring yet.
- **Shared prompts.** The 9 SDD prompts live at `src/ai_harness/resources/prompts/sdd/*.md` and are the single source of truth for all adapters.

### Agent count correction

`opencode.json` contains **16 agents total**, not the "10 phase subagents + 17 total" sometimes referenced.

| Agent | OpenCode mode | Hidden | Prompt source |
|---|---|---|---|
| `sdd-orchestrator` | primary | no | `{file:{{HOME}}/.config/opencode/prompts/sdd/sdd-orchestrator.md}` |
| `sdd-explore` | subagent | yes | `{file:.../sdd-explore.md}` |
| `sdd-propose` | subagent | yes | `{file:.../sdd-propose.md}` |
| `sdd-spec` | subagent | yes | `{file:.../sdd-spec.md}` |
| `sdd-design` | subagent | yes | `{file:.../sdd-design.md}` |
| `sdd-tasks` | subagent | yes | `{file:.../sdd-tasks.md}` |
| `sdd-apply` | subagent | yes | `{file:.../sdd-apply.md}` |
| `sdd-verify` | subagent | yes | `{file:.../sdd-verify.md}` |
| `sdd-archive` | subagent | yes | `{file:.../sdd-archive.md}` |
| `jd-fix-agent` | subagent | yes | inline (short) |
| `jd-judge-a` | subagent | yes | inline (short) |
| `jd-judge-b` | subagent | yes | inline (short) |
| `review-risk` (R1) | subagent | yes | inline (long) |
| `review-readability` (R2) | subagent | yes | inline (long) |
| `review-reliability` (R3) | subagent | yes | inline (long) |
| `review-resilience` (R4) | subagent | yes | inline (long) |

**Known drift:** `sdd-orchestrator.permission.task` lists `sdd-init` and `sdd-onboard` as allowed, but no such agents exist in the `agent` block. The orchestrator prompt states both run **inline** in the primary agent, so they are not mirrored as separate copilot-cli agents.

### copilot-cli platform constraints (that shape the adapter)

- Custom agents are `*.agent.md` files with YAML frontmatter (`name`, `description`, `tools`, optional `mcp-servers`/`target`) and a Markdown body that **is** the system prompt.
- Hard 30,000-character limit per agent prompt (frontmatter + body).
- No per-agent `model` field is honored in copilot-cli; only the global model (via `/model` or `--model`) is used.
- No `hidden: true` flag; every custom agent appears in the `/agent` picker.
- No declarative `permission.*` block; access control must be implemented with JSON hooks (`preToolUse`, `subagentStart`, `subagentStop`, etc.).
- No plugin system; `model-variants.ts` has no copilot-cli equivalent.
- No user-defined slash commands; SDD entrypoints become natural-language instructions inside the orchestrator body.
- Subagent delegation exists via the `task` tool, but there is no config-level task allowlist — enforcement is prompt + hooks.
- Skills use the same `SKILL.md` standard and can live at `~/.copilot/skills/` (plus other standard paths).

### Mapping: OpenCode concept → copilot-cli concept

| OpenCode concept | OpenCode location / key | copilot-cli equivalent | Notes |
|---|---|---|---|
| Single config file | `.config/opencode/opencode.json` | None — spread across `~/.copilot/agents/*.agent.md` and `~/.copilot/hooks/*.json` | No 1:1 JSON analogue |
| Primary orchestrator | `agent.sdd-orchestrator.mode: primary` | `~/.copilot/agents/sdd-orchestrator.agent.md` | Body embeds `sdd-orchestrator.md`; natural-language entrypoints replace slash commands |
| Phase subagent | `agent.sdd-<phase>` with `prompt: {file:...}` | `~/.copilot/agents/sdd-<phase>.agent.md` | Body embeds shared `prompts/sdd/sdd-<phase>.md` |
| Judgment-day agents | Inline `prompt` in `opencode.json` | `~/.copilot/agents/jd-fix-agent.agent.md`, `jd-judge-a.agent.md`, `jd-judge-b.agent.md` | Inline prompts become body |
| Reviewer agents | Inline `prompt` in `opencode.json` | `~/.copilot/agents/review-*.agent.md` | Same as above |
| Permission policy | `permission.*` in `opencode.json` | `~/.copilot/hooks/sdd-pre-tool-use.json` (and optionally `subagentStart`/`subagentStop`) | JSON hooks must match tool name + arguments |
| Model assignments block | `blocks/sdd-model-assignments.md` | Omitted (per Q3) | Per-agent `model` is ignored in copilot-cli |
| Model-variants plugin | `plugins/model-variants.ts` | Omitted (per Q4-b) | No plugin system |
| Global instructions | `.config/opencode/AGENTS.md` | `.copilot/copilot-instructions.md` | Already installed from `resources/AGENTS.md` |
| Skills | `.agents/skills/` | `.copilot/skills/` | Same `SKILL.md` format; add to `CopilotInstaller` |
| Prompt indirection | `{file:{{HOME}}/.config/opencode/prompts/sdd/...}` | None | Body embedding is the only faithful option |
| Slash commands | `/sdd-new`, `/sdd-continue`, etc. | Natural-language triggers in orchestrator body | Per Q5 |
| `hidden: true` | Agent metadata | Not supported | All 16 agents visible in `/agent` picker |

### Source adapter layout (recommended)

Because instructions and skills are already shared resources, the copilot-cli adapter source should contain only the platform-specific artifacts:

```
src/ai_harness/resources/agent-clis/copilot-cli/
├── README.md
├── agents/
│   ├── sdd-orchestrator.agent.md   # frontmatter + embedded sdd-orchestrator.md
│   ├── sdd-explore.agent.md
│   ├── sdd-propose.agent.md
│   ├── sdd-spec.agent.md
│   ├── sdd-design.agent.md
│   ├── sdd-tasks.agent.md
│   ├── sdd-apply.agent.md
│   ├── sdd-verify.agent.md
│   ├── sdd-archive.agent.md
│   ├── jd-fix-agent.agent.md
│   ├── jd-judge-a.agent.md
│   ├── jd-judge-b.agent.md
│   ├── review-risk.agent.md
│   ├── review-readability.agent.md
│   ├── review-reliability.agent.md
│   └── review-resilience.agent.md
└── hooks/
    └── sdd-pre-tool-use.json        # fail-closed allowlist + path deny policy
```

`instructions/` and `skills/` are **not** duplicated here; they continue to come from `resources/AGENTS.md` and `resources/skills/`. Creating local copies would introduce drift without adding value.

### Prompt embedding strategy

**Recommendation: install-time composition from the shared single source of truth.**

1. Keep `src/ai_harness/resources/prompts/sdd/*.md` unchanged as the canonical prompt text.
2. Store a small frontmatter template per agent under `agent-clis/copilot-cli/agents/*.agent.md` (or generate the frontmatter in code).
3. At install time, `CopilotInstaller` reads the shared prompt and writes the installed `~/.copilot/agents/*.agent.md` as `frontmatter + "\n" + prompt_body`.
4. For judgment-day and reviewer agents, extract their inline prompts from `opencode.json` into small markdown files under the adapter so the installer can treat all agents uniformly.

**Rationale:** This is the closest copilot-cli analogue to OpenCode's install-time prompt placement. OpenCode writes prompt files into `~/.config/opencode/prompts/sdd/` and references them; copilot-cli has no reference syntax, so the same "write into place" semantics require embedding. Install-time composition preserves the single source of truth in the repo and avoids maintaining two divergent copies of every prompt.

**Character budget (verified):**

| Prompt | Chars | % of 30k limit |
|---|---|---|
| `sdd-apply.md` | 17,228 | 57.4% |
| `sdd-archive.md` | 9,926 | 33.1% |
| `sdd-design.md` | 8,143 | 27.1% |
| `sdd-explore.md` | 6,355 | 21.2% |
| `sdd-orchestrator.md` | 15,473 | 51.6% |
| `sdd-propose.md` | 10,243 | 34.1% |
| `sdd-spec.md` | 10,421 | 34.7% |
| `sdd-tasks.md` | 10,697 | 35.7% |
| `sdd-verify.md` | 21,285 | 71.0% |

Even with ~200–400 characters of YAML frontmatter, every agent stays comfortably under the 30,000-character limit.

### Installation wiring needed

`src/ai_harness/artifacts/installers/copilot.py` must expand its manifest to include:

1. `resources/AGENTS.md` → `~/.copilot/copilot-instructions.md` (already done).
2. `resources/skills/` → `~/.copilot/skills/` (new `DirArtifact`).
3. Composed `agent-clis/copilot-cli/agents/*.agent.md` → `~/.copilot/agents/*.agent.md` (new `FileArtifact`s, generated on the fly).
4. `agent-clis/copilot-cli/hooks/*.json` → `~/.copilot/hooks/*.json` (new `FileArtifact`s or `DirArtifact`).

`src/ai_harness/artifacts/catalog.py` should add `.copilot/skills` to `SKILLS_TARGET_DIRS` so the existing e2e assertion pattern can optionally cover it.

### TDD / e2e contract

Per the strict-TDD rule, `sdd-apply` must first create failing e2e tests in `e2e/test_copilot_cli_lifecycle.py` mirroring `e2e/test_harness_lifecycle.py`. The new test should assert:

- Fresh install creates `~/.copilot/copilot-instructions.md`, `~/.copilot/skills/`, `~/.copilot/agents/*.agent.md`, and `~/.copilot/hooks/*.json`.
- Reinstall overrides stale project files while preserving user-authored skills/instructions.
- Uninstall removes project files and restores pre-existing backups.

### Risks and unknowns

- **Shared prompts are not transport-agnostic.** They reference `~/.config/opencode/skills/` and "OpenCode's native `task` tool." Embedding them verbatim in copilot-cli agents would send them to the wrong skill paths and use platform-specific phrasing. The proposal must decide whether to (a) patch the shared prompts to be generic (add `~/.copilot/skills/` and `~/.claude/skills/` to scan paths, replace tool wording) or (b) prepend a copilot-specific override block in each agent body. Option (a) is cleaner but touches files used by other adapters; option (b) avoids shared-file changes but risks contradictory instructions.
- **Install-time composition is new.** The generic installer expects a stable source file so uninstall content-matching works. Composition must be deterministic (same frontmatter + same prompt → same bytes). This is achievable but needs unit-test coverage.
- **No per-agent model enforcement.** Phases that rely on specific models in OpenCode will run under copilot-cli's global model. The user explicitly accepted omitting `sdd-model-assignments.md`, but this is a functional gap to document.
- **No hidden agents.** All 16 custom agents will appear in the `/agent` picker, creating UX clutter that OpenCode avoids.
- **No declarative task allowlist.** Hooks must implement the allow/deny policy; any gap in hook coverage makes delegation opportunistic rather than enforced.
- **Requested source layout ambiguity.** The user's "`agents/`, `hooks/`, `instructions/`, `skills/`" directories for the source adapter conflict with the current shared-resource pattern for instructions and skills. The recommended interpretation is to keep instructions/skills in the existing shared locations and only add `agents/` and `hooks/` to the adapter.

### Open questions for the user

No blockers; `sdd-propose` can proceed. The proposal should resolve the prompt-transport-agnostic strategy (risk #1) and confirm the source-adapter layout interpretation.

### Ready for Proposal

Yes. The proposal should cover:

1. Exact source adapter directory layout (`agents/` + `hooks/`; reuse shared `AGENTS.md` and `resources/skills/`).
2. Install-time composition strategy for `.agent.md` files.
3. Hook JSON design (tool allowlist, path deny policy, subagent guards).
4. Prompt patching / override strategy for OpenCode-specific references.
5. E2e test contract for `e2e/test_copilot_cli_lifecycle.py`.
6. Rollback plan: remove new adapter files and revert `CopilotInstaller`/`catalog.py` changes.
