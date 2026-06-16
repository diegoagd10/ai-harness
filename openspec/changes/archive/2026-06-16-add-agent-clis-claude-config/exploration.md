# Exploration: Claude Code agent-clis parity (`agent-clis/claude`)

## Summary

`ai-harness install` today stages a full SDD agent graph for **OpenCode** (`src/ai_harness/resources/agent-clis/opencode/opencode.json`) and wires it into `~/.config/opencode/...` via `src/ai_harness/main.py`. The repo already installs `.claude/CLAUDE.md` and `.claude/skills/` for Claude Code, but the **agent graph** (subagents + an orchestrator entrypoint) has no Claude Code equivalent. This change will stage that graph as `.claude/agents/*.md` (+ likely a `.claude/commands/` entrypoint) and add the matching `main.py` install/uninstall wiring, reusing the existing `{{HOME}}`/backup pattern. This phase only INVESTIGATES — it writes no code under `src/`, `tests/`, or `main.py`.

## Current State

### OpenCode agent graph (the PARITY TARGET)

Source: `src/ai_harness/resources/agent-clis/opencode/opencode.json`. The whole pipeline is "prompts + config" — no custom runtime. The JSON defines **16 agents**: 1 primary + 15 hidden subagents.

| Agent | Mode | Hidden | Model (in JSON) | Tools | Prompt source |
|---|---|---|---|---|---|
| `sdd-orchestrator` | **primary** | no | `openai/gpt-5.5` | bash, edit, read, task, write | `{file:{{HOME}}/.config/opencode/prompts/sdd/sdd-orchestrator.md}` |
| `sdd-explore` | subagent | yes | `opencode-go/kimi-k2.7-code` | bash, edit, read, write | `{file:...sdd-explore.md}` |
| `sdd-propose` | subagent | yes | `opencode-go/deepseek-v4-pro` | bash, edit, read, write | `{file:...sdd-propose.md}` |
| `sdd-spec` | subagent | yes | `opencode-go/deepseek-v4-pro` | bash, edit, read, write | `{file:...sdd-spec.md}` |
| `sdd-design` | subagent | yes | `opencode-go/deepseek-v4-pro` | bash, edit, read, write | `{file:...sdd-design.md}` |
| `sdd-tasks` | subagent | yes | `opencode-go/deepseek-v4-pro` | bash, edit, read, write | `{file:...sdd-tasks.md}` |
| `sdd-apply` | subagent | yes | `opencode-go/deepseek-v4-pro` | bash, edit, read, write | `{file:...sdd-apply.md}` |
| `sdd-verify` | subagent | yes | `opencode-go/kimi-k2.6` | bash, edit, read, write | `{file:...sdd-verify.md}` |
| `sdd-archive` | subagent | yes | `opencode-go/deepseek-v4-flash` | bash, edit, read, write | `{file:...sdd-archive.md}` |
| `jd-judge-a` | subagent | yes | (default) | bash, read | **inline** (short) |
| `jd-judge-b` | subagent | yes | (default) | bash, read | **inline** (short) |
| `jd-fix-agent` | subagent | yes | (default) | bash, edit, read, write | **inline** (short) |
| `review-risk` (R1) | subagent | yes | (default) | bash, read | **inline** (long) |
| `review-readability` (R2) | subagent | yes | (default) | bash, read | **inline** (long) |
| `review-reliability` (R3) | subagent | yes | (default) | bash, read | **inline** (long) |
| `review-resilience` (R4) | subagent | yes | (default) | bash, read | **inline** (long) |

**Count reconciliation (IMPORTANT — corrects the "expected ~17" brief and the README):**
- The brief and `agent-clis/opencode/README.md` both say "17 hidden subagents (9/10 SDD phases + sdd-init + 3 judgment-day + 4 reviewers)". The JSON does **not** match that.
- Actual JSON: **8 SDD-phase subagents** (explore, propose, spec, design, tasks, apply, verify, archive) + **3 judgment-day** + **4 reviewers** = **15 hidden subagents**, plus the `sdd-orchestrator` primary = **16 total**.
- `sdd-init` and `sdd-onboard` are NOT defined as agents. They appear only in `sdd-orchestrator.permission.task` (allow-list) and the orchestrator prompt states they run **INLINE** in the orchestrator (`prompts/sdd/sdd-orchestrator.md` line 12: "`sdd-init` runs inline"). So there is no `sdd-init`/`sdd-onboard` agent file to mirror. The orchestrator's task allow-list is broader than the set of agents that actually exist.
- The README's "10 SDD phases" and "17 subagents" figures are stale; the parity target is the 15 subagents + orchestrator actually in the JSON.

**Prompt indirection.** The 8 SDD phases + the orchestrator point at shared prompt files via `{file:{{HOME}}/.config/opencode/prompts/sdd/<phase>.md}`. Those files are the single source of truth at `src/ai_harness/resources/prompts/sdd/*.md` (9 files: the 8 phases + `sdd-orchestrator.md`) and are written to `~/.config/opencode/prompts/sdd/` at install time. The judgment-day and reviewer agents carry their (short/medium) prompts **inline** in the JSON — there is no shared file for them.

### Supporting OpenCode assets (in `agent-clis/opencode/`)

- `blocks/sdd-model-assignments.md` — a prompt block telling the orchestrator to read per-agent models from `opencode.json` at session start. OpenCode-specific (references `opencode.json`); not directly portable.
- `plugins/model-variants.ts` + `plugins/model-variants.test.ts` — an **OpenCode-runtime plugin** that imports `@opencode-ai/plugin` and writes a model-variant cache. Has no Claude Code analogue (Claude Code has no plugin SDK of this shape). Out of scope for parity.
- `README.md` — describes the graph (with the stale counts noted above) and the `{{HOME}}` placeholder mechanism.
- The five user-facing slash-command templates (`/sdd-new`, `/sdd-continue`, `/sdd-status`, `/sdd-init`, `/sdd-onboard`) are described in the README as living at a repo-root `prompts/commands/*.md` and being generated into `~/.config/opencode/commands/`. **That directory does NOT exist yet** — `src/ai_harness/resources/prompts/` contains only `sdd/`. They are aspirational in both harnesses.

### Existing Claude Code install (already wired)

`src/ai_harness/main.py` already installs, for Claude Code:
- `.claude/CLAUDE.md` (via `AGENTS_MD_TARGETS`, copied from `resources/AGENTS.md`)
- `.claude/skills/` (via `SKILLS_TARGET_DIRS`, copied from `resources/skills/`)

So the persona and skills are present for Claude Code today. The **only** gap is the agent graph: the subagents and an orchestrator entrypoint.

### Existing OpenCode install wiring pattern (`main.py`)

Constants (lines 10-33):
- `OPENCODE_JSON_SRC` → `OPENCODE_JSON_TARGET` = `.config/opencode/opencode.json`
- `OPENCODE_SDD_PROMPTS_SRC` (`resources/prompts/sdd`) → `OPENCODE_SDD_PROMPTS_TARGET_DIR` = `.config/opencode/prompts/sdd`
- `OPENCODE_AGENTS_MD_*` for `.config/opencode/AGENTS.md`
- Suffix constants: `OPENCODE_BACKUP_SUFFIX = ".ai-harness-backup"`, `OPENCODE_CONFLICT_BACKUP_SUFFIX = ".ai-harness-conflict-backup"`

Behavior (the reusable pattern):
1. `{{HOME}}` literal in `opencode.json` is `.replace("{{HOME}}", str(home))` at install time (lines 77-79).
2. Per-file, when the existing target differs from the new content: copy the old file to `<name>.ai-harness-backup`; if that backup already exists, copy to `<name>.ai-harness-conflict-backup[.N]` via `next_available_path` (lines 41-49, 80-94, 128-143).
3. `uninstall` removes a target only if its content still matches what we installed, then restores from `.ai-harness-backup` if present (lines 168-208). Conflict-backups are never auto-restored (audit trail).

This exact pattern is what the new `.claude/agents/` (and possibly `.claude/commands/`) wiring should reuse.

## Affected Areas

- `src/ai_harness/resources/agent-clis/opencode/opencode.json` — read-only **parity source**: agent names, models, tools, prompt indirection.
- `src/ai_harness/resources/prompts/sdd/*.md` — shared phase + orchestrator prompts (single source of truth). The Claude agents must consume these.
- `src/ai_harness/main.py` — install/uninstall: add new source/target constants + copy loops for `.claude/agents/` and (optionally) `.claude/commands/`, reusing the backup/`{{HOME}}` pattern.
- **NEW (to be staged in later phases):** `src/ai_harness/resources/agent-clis/claude/agents/*.md` (15 subagents) and possibly `src/ai_harness/resources/agent-clis/claude/commands/*.md` (orchestrator entrypoint + user-facing slash commands).
- `tests/` — install/uninstall coverage + e2e (`e2e/docker-test.sh`), per `openspec/config.yaml` strict_tdd.

## Claude Code subagent format mapping (evidence-backed)

Sources: official Claude Code docs — `code.claude.com/docs/en/sub-agents.md`, `.../memory.md`, `.../skills.md` (verified via claude-code-guide this session).

**Subagent file format.** Project/global subagents live in `.claude/agents/<name>.md` (global: `~/.claude/agents/`). YAML frontmatter supports `name` (required), `description` (required), `tools`, `disallowedTools`, `model`, `permissionMode`, `skills`, and more. The **Markdown body after the frontmatter becomes the subagent's system prompt.**
- `model`: accepts `sonnet` | `opus` | `haiku` | `fable` | a full model id (e.g. `claude-opus-4-8`) | `inherit` (default). OpenCode's `opencode-go/*` and `openai/gpt-5.5` model ids do NOT map 1:1 — the Claude graph must choose Claude model aliases (decision for design, not explore).
- `tools`: comma/space-separated string or YAML list; an **allow-list** (only listed tools available). Omit → inherits all tools. OpenCode `read/edit/write/bash/task` maps to Claude `Read/Edit/Write/Bash/Agent` (the Agent tool is OpenCode's `task`). OpenCode `edit:deny` on read-only reviewers maps to a Read/Bash-only tool list.

**Per-agent mapping.** Each OpenCode subagent → one `.claude/agents/<name>.md`:
- 8 SDD phases + the 4 reviewers + 3 judgment-day agents → 15 agent files. Same names work as-is.
- The reviewer/judgment-day inline prompts in `opencode.json` become the Markdown body verbatim.
- The 8 SDD phases need their shared prompt content in the body — see the prompt-reuse finding below.

### KEY FINDING — can a Claude agent body REFERENCE the shared prompt files? **NO (not via @import).**

This is the load-bearing constraint for parity. Evidence:
- The `@path/to/file` import syntax is **CLAUDE.md-only** (`memory.md`: "CLAUDE.md files can import additional files using `@path/to/import` syntax"). It is NOT processed inside subagent bodies.
- A subagent `.md` body is treated as **literal system-prompt text**. There is no `{file:...}` indirection equivalent to OpenCode's. So a Claude agent CANNOT point at `~/.claude/.../sdd/<phase>.md` the way OpenCode does.
- The same applies to `.claude/commands/*.md` / skill bodies: literal text, no `@file` import.

**Available indirection mechanisms (the real options to mirror `{file:...}`):**
1. **Inline / duplicate at install time.** `ai-harness install` reads `resources/prompts/sdd/<phase>.md` and writes the agent file with that content **embedded** in the body (frontmatter prepended). The shared prompt stays the single source of truth in the repo; the duplication happens only in the generated install artifact, not in the repo. This is the closest faithful analogue to how OpenCode's prompts are "written into place" at install — just embedded instead of referenced.
2. **Dynamic command injection** via `` !`cmd` `` in the body — Claude Code runs the command at load time and inserts stdout. E.g. body = `` !`cat ~/.claude/prompts/sdd/sdd-explore.md` ``. This achieves true runtime indirection (single installed source file, no duplication), mirroring `{file:...}` semantics, but depends on the `!`cmd`` feature being enabled/allowed and a stable installed path for the prompts. Higher risk, needs validation.
3. **`skills:` frontmatter / shared skill.** Put the phase prompt in a skill and reference it from the agent's `skills:` field. Indirect, but changes the artifact shape and may not carry the full system-prompt semantics.

Recommendation for design (not decided here): option 1 (install-time embedding) is the safest faithful parity; option 2 (`!`cmd`` injection) is the truest mirror of `{file:...}` but must be validated against the Claude Code version shipped to users.

## Orchestrator entrypoint options (OpenCode `mode: "primary"` has NO direct equivalent)

Claude Code has **no `mode: primary`**. There is no agent that is automatically "the main driver" from a config file alone. Enumerated concrete options (decision deferred to the maintainer):

| # | Option | How it works | Pros | Cons |
|---|---|---|---|---|
| A | **`.claude/commands/` slash command** (e.g. `/sdd-new`, `/sdd-continue`) that loads the orchestrator prompt and drives `Agent`-tool delegation to the 15 subagents | User types `/sdd-new foo`; command body = orchestrator instructions + `$ARGUMENTS`; orchestrator logic delegates via the Agent tool | Explicit, discoverable entrypoint; mirrors the README's intended 5 slash commands; user controls when SDD starts | Slash-command body is literal (no `@import`) so orchestrator prompt must be embedded at install (same constraint as agents); maintainer must author command templates that don't exist yet |
| B | **`claude --agent sdd-orchestrator`** — install the orchestrator as a normal subagent and launch it as the MAIN session | `claude --agent <name>` makes a custom agent the orchestrator session; it can spawn subagents | Closest behavioral match to OpenCode `primary` (an agent IS the main thread); reuses the existing `sdd-orchestrator.md` prompt as a body | Requires a CLI invocation flag, not just files; not auto-discoverable; awkward for "just open Claude Code and go"; still needs the prompt embedded |
| C | **Rely on existing `.claude/CLAUDE.md` + skills routing** — no orchestrator agent; the global CLAUDE.md orchestration rules + `engram`/skills route the user to delegate to SDD subagents | Already installed today; CLAUDE.md has an "Orchestration" coordinator section | Zero new entrypoint artifacts; leverages what's already wired | No SDD-specific entrypoint; user must know to ask for SDD by hand; loses the curated preflight/hard-gate flow the orchestrator prompt encodes; weakest parity |
| D | **`context: fork` + `agent:` skill/command** — a skill (`.claude/skills/sdd-orchestrator/SKILL.md`) that forks into the orchestrator agent | Skill frontmatter `context: fork` + `agent: sdd-orchestrator` runs the orchestrator in a subagent context | Uses the documented skill→subagent delegation; auto-loadable by Claude when relevant | Indirection adds a layer; fork semantics differ from a true primary session; behavior needs validation |
| E | **Hybrid A+B** — ship both a `.claude/commands/sdd-*.md` set AND the orchestrator as a launchable agent | Slash commands for interactive use; `--agent` for headless/CI | Covers both interactive and headless | Most artifacts to build and maintain |

No option is selected here — this is the maintainer's call before `sdd-propose`. Options A and E best match the README's stated 5-slash-command intent; B is the truest behavioral mirror of `mode: primary`.

## main.py install/uninstall wiring needed (new constants, reusing the existing pattern)

Mirror the OpenCode block. Proposed NEW constants (names for design to confirm):

```
CLAUDE_AGENTS_SRC          = RESOURCES_DIR / "agent-clis" / "claude" / "agents"
CLAUDE_AGENTS_TARGET_DIR   = Path(".claude/agents")
# optional, if an orchestrator entrypoint via slash commands is chosen:
CLAUDE_COMMANDS_SRC        = RESOURCES_DIR / "agent-clis" / "claude" / "commands"
CLAUDE_COMMANDS_TARGET_DIR = Path(".claude/commands")
```

Install loop (per file, reusing the existing helpers):
- `mkdir -p` the target dir (as the OpenCode prompts loop does, line 122-123).
- For each agent/command file: substitute `{{HOME}}` if the body uses absolute installed paths (only needed if option 2 `!`cmd`` injection or absolute path refs are chosen; option 1 embedding needs no substitution).
- Reuse the backup logic: if target exists and differs, copy to `<name>.ai-harness-backup`; else `.ai-harness-conflict-backup[.N]` via `next_available_path` (same as lines 128-143).
- Reuse `OPENCODE_BACKUP_SUFFIX` / `OPENCODE_CONFLICT_BACKUP_SUFFIX` (or rename them to a harness-neutral `BACKUP_SUFFIX` / `CONFLICT_BACKUP_SUFFIX` — a small refactor design may choose).

Uninstall loop: remove each installed file only if content still matches; restore from `.ai-harness-backup` if present (same shape as lines 196-208). Add the agent (and command) names to the removal set the way `project_skill_names` drives skill removal (lines 158-166).

**Note on the prompt-reuse choice and wiring.** If design picks option 1 (embed prompts at install), the install loop must *compose* each agent file from (frontmatter template) + (shared `prompts/sdd/<phase>.md` content) at install time, rather than a flat `copyfile`. That is a meaningful behavior change vs the current pure-copy loops and should be called out in the proposal. If design picks option 2 (`!`cmd`` injection), the agent files can be flat-copied (with `{{HOME}}` substitution for the prompt path) — closer to the current loops.

## Approaches

1. **Faithful 1:1 graph, prompts embedded at install (option 1 reuse + entrypoint A or E)** — 15 `.claude/agents/*.md` + slash-command entrypoint(s); install composes agent bodies from shared prompts.
   - Pros: maximal parity; single source of truth preserved in repo; no dependency on `!`cmd``.
   - Cons: install loop becomes a compose step (new logic + tests); duplication in the installed artifact.
   - Effort: Medium-High.

2. **Faithful 1:1 graph, `!`cmd`` runtime injection (option 2 reuse + entrypoint A/B)** — agent bodies reference installed shared prompts via `` !`cat ...` ``.
   - Pros: truest mirror of OpenCode `{file:...}`; flat-copy install; no artifact duplication.
   - Cons: depends on `!`cmd`` being enabled/permitted in the user's Claude Code; needs validation; absolute-path/`{{HOME}}` fragility.
   - Effort: Medium (if the feature works as documented).

3. **Minimal — rely on CLAUDE.md/skills routing (entrypoint C), ship only subagents** — no orchestrator entrypoint artifact.
   - Pros: least to build; CLAUDE.md already installed.
   - Cons: weakest parity; loses preflight/hard-gate orchestration; poor discoverability.
   - Effort: Low.

## Recommendation

Proceed to `sdd-propose`. Before proposing, the maintainer MUST decide two coupled questions this exploration deliberately leaves open:
1. **Prompt reuse mechanism** — embed at install (option 1) vs `!`cmd`` injection (option 2). This determines whether the install loop is a compose step or a flat copy.
2. **Orchestrator entrypoint** — A (slash commands), B (`--agent` primary), C (CLAUDE.md routing), D (skill fork), or E (hybrid).

The exploration confirms the parity target is **15 subagents + 1 orchestrator entrypoint** (not 17/18), and that **Claude agent bodies cannot `@import` the shared prompts** — so some install-time composition or `!`cmd`` indirection is unavoidable.

## Risks

- **Stale counts in the brief/README**: building "17 subagents" would over-produce. The real graph is 15 hidden subagents + orchestrator; `sdd-init`/`sdd-onboard` are inline, not agents.
- **No native prompt indirection in Claude agents**: the `{file:...}` analogue does not exist; the chosen mechanism (embed vs `!`cmd``) must be validated against the shipped Claude Code version. `!`cmd`` injection may be disabled by permissions.
- **Model id mismatch**: OpenCode `opencode-go/*` / `openai/gpt-5.5` do not map to Claude aliases; the graph must pick `opus/sonnet/haiku/inherit` per agent — a design decision, with cost/latency tradeoffs.
- **Install loop complexity**: composing agent bodies from shared prompts is new logic vs the current pure-copy loops; strict_tdd requires unit + e2e coverage (`e2e/docker-test.sh`).
- **OpenCode-only assets** (`plugins/model-variants.ts`, `blocks/sdd-model-assignments.md`) have no Claude analogue; excluding them is correct but should be stated explicitly so parity isn't judged against them.
- **Entrypoint discoverability**: option C loses the curated orchestrator flow; options A/E require authoring slash-command templates that do not yet exist.

## Follow-up (out of scope unless a finding forces it in)

- **Per-harness `--harness claude,opencode,copilot` selection.** The old Go CLI (memory #11) had this; the current Python CLI installs unconditionally for all harnesses. Adding the Claude agent graph makes the install heavier, which may justify selective install — but it is NOT required for this change. Track as a separate proposal.

## Ready for Proposal

**Yes** — with the two open decisions (prompt-reuse mechanism + orchestrator entrypoint) surfaced for the maintainer to resolve at `sdd-propose`. No blockers.
