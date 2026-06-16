# Design: Claude Code SDD agent graph parity (`agent-clis/claude`)

## Technical Approach

Stage a Claude SDD graph under `resources/agent-clis/claude/`: an orchestrator **skill** (main thread) plus **15** `.claude/agents/*.md` subagents. At `ai-harness install`, the 8 SDD-phase agents are **composed** (frontmatter + shared `prompts/sdd/<phase>.md`) and written to `~/.claude/agents/`; the 7 inline agents (3 judgment-day + 4 reviewers) and the orchestrator skill are flat-copied. All wiring reuses the existing OpenCode `{{HOME}}` + `.ai-harness-backup`/`.ai-harness-conflict-backup[.N]` helpers. Implements `specs/agent-clis-claude` and `specs/cli-sdd`. Red-first per `strict_tdd`.

## Architecture Decisions

### Decision 1 — Per-agent Claude model alias

OpenCode model ids are a parity *signal* (heavy-reasoning phases ran a `-pro`/`-code` tier; archive ran `-flash`; judges/reviewers ran default). We map to Claude aliases by reasoning load, not 1:1.

| Agent (.claude/agents) | OpenCode model | Claude `model` | Rationale |
|---|---|---|---|
| sdd-explore | kimi-k2.7-code | `opus` | Open-ended codebase reasoning; depth pays off |
| sdd-propose | deepseek-v4-pro | `opus` | Synthesizes scope/risk/alternatives |
| sdd-spec | deepseek-v4-pro | `opus` | Contract correctness is load-bearing |
| sdd-design | deepseek-v4-pro | `opus` | Architecture decisions w/ rationale |
| sdd-tasks | deepseek-v4-pro | `sonnet` | Mechanical decomposition from spec+design |
| sdd-apply | deepseek-v4-pro | `inherit` | Runs strict TDD; match the driving session's tier |
| sdd-verify | kimi-k2.6 | `sonnet` | Structured check against spec; bounded |
| sdd-archive | deepseek-v4-flash | `haiku` | Cheapest tier; file moves + delta merge |
| jd-judge-a / jd-judge-b | default | `opus` | Adversarial review quality dominates cost |
| jd-fix-agent | default | `inherit` | Surgical fix; match session tier |
| review-risk (R1) | default | `opus` | Security findings must not be missed |
| review-readability (R2) | default | `sonnet` | Pattern-matching against rule list |
| review-reliability (R3) | default | `sonnet` | Pattern-matching against rule list |
| review-resilience (R4) | default | `sonnet` | Pattern-matching against rule list |

**Rationale**: opus for heavy reasoning / non-recoverable misses (explore→design, judges, R1); sonnet for mechanical-but-structured (tasks, verify, R2–R4); haiku for the trivial archive; `inherit` only where the agent must track the driving session (apply, jd-fix). Orchestrator skill = no `model` (runs in the user's main thread). **Alternatives rejected**: all-`inherit` (loses cost control, no parity signal); literal model ids (brittle across releases — aliases are version-stable per Claude Code docs).

### Decision 2 — Compose-template shape

Frontmatter templates live as authored `.md` files in `resources/agent-clis/claude/agents/`. The 8 phase files contain **frontmatter only** (a leading `---`/`---` block + trailing newline, no body). The 7 inline files contain frontmatter **and** their full body.

Install join algorithm (deterministic, idempotent — content-addressed write):
```
for src in agent-clis/claude/agents/*.md:
    fm = src.read_text()                       # always the frontmatter (+ inline body)
    phase = phase_name_if_shared_prompt(src.stem)   # e.g. "sdd-design" → prompts/sdd/sdd-design.md
    body = (fm.rstrip()+"\n\n"+ PROMPTS_SDD/(phase+".md").read_text()) if phase else fm
    body = body.replace("{{HOME}}", str(home))
    write_with_backup(home/".claude/agents"/src.name, body)   # reuse backup/conflict helper
```
`phase_name_if_shared_prompt` returns the stem only when a same-named file exists in `prompts/sdd/` (explore, propose, spec, design, tasks, apply, verify, archive) — the 7 inline stems have no shared prompt, so they pass through unchanged. Idempotent: re-running yields byte-identical output, so the diff check is a no-op (no spurious backup). **Alternatives rejected**: a separate `templates/` + `bodies/` split (two dirs for one concept — pushes ritual up); detecting phases by a hardcoded list in `main.py` (duplicates the `prompts/sdd/` directory as source of truth — derive from the filesystem instead).

### Decision 3 — Constant naming (minimal diff)

**Keep `OPENCODE_BACKUP_SUFFIX` / `OPENCODE_CONFLICT_BACKUP_SUFFIX` untouched and reuse them as-is** for the Claude targets. Add only new **path** constants (`CLAUDE_AGENTS_SRC`, `CLAUDE_AGENTS_TARGET_DIR`, `CLAUDE_ORCH_SKILL_SRC`, `CLAUDE_ORCH_SKILL_TARGET_DIR`). **Rationale**: the suffix *values* (`.ai-harness-backup`, `.ai-harness-conflict-backup`) are already harness-neutral — only the variable name carries the `OPENCODE_` prefix, and renaming would touch ~12 existing lines for zero behavior change, inflating the enforced 400-line review budget. The spec requires the *same* suffix strings for Claude, so sharing the exact constant is correct, not a smell. A rename to `BACKUP_SUFFIX` is a defensible follow-up but is pure churn here. **Rejected**: parallel `CLAUDE_*` suffix constants (duplicate identical literals — change amplification if the suffix ever changes).

### Decision 4 — Orchestrator-skill install path/target

Skill-only, no `.claude/commands/` entrypoint (per locked decision; matches OpenCode `mode: primary` having no command template today).

- **Source**: `resources/agent-clis/claude/sdd-orchestrator/SKILL.md` (authored: frontmatter `name`/`description` + orchestrator body sourced from `prompts/sdd/sdd-orchestrator.md`, embedded at authoring time since the orchestrator is a skill, not a composed phase agent).
- **Target**: `~/.claude/skills/sdd-orchestrator/SKILL.md` (Claude global skill dir layout `<name>/SKILL.md` — same as the already-installed `SKILLS_TARGET_DIRS`).
- Skill frontmatter MUST NOT set `context: fork` (runs in the main thread).

## Data Flow — install compose

```
resources/agent-clis/claude/agents/<name>.md ──┐
   (frontmatter; +body if inline)              │  same stem in prompts/sdd/ ?
prompts/sdd/<phase>.md ─────────────────────────┤── yes ─► join(fm, shared) ─┐
                                                └── no  ─► fm verbatim ───────┤
                                                                              ▼
                                            {{HOME}} substitute ─► write_with_backup ─► ~/.claude/agents/<name>.md

resources/agent-clis/claude/sdd-orchestrator/SKILL.md ─► flat copy ─► ~/.claude/skills/sdd-orchestrator/SKILL.md
```

## File Changes

| File | Action | Description |
|---|---|---|
| `resources/agent-clis/claude/agents/*.md` (15) | Create | 8 phase frontmatter-only + 7 inline (judge/reviewer) |
| `resources/agent-clis/claude/sdd-orchestrator/SKILL.md` | Create | Main-thread orchestrator skill (no `context: fork`) |
| `resources/agent-clis/claude/README.md` | Create | Graph description + `{{HOME}}` mechanism |
| `src/ai_harness/main.py` | Modify | New path constants + `_compose_agent_body`/`write_with_backup` helper + Claude install/uninstall blocks |
| `tests/`, `e2e/docker-test.sh` | New/Modify | Compose, backup, uninstall coverage |

## Interfaces / Contracts (new in `main.py`)

```python
CLAUDE_AGENTS_SRC          = RESOURCES_DIR / "agent-clis" / "claude" / "agents"
CLAUDE_AGENTS_TARGET_DIR   = Path(".claude/agents")
CLAUDE_ORCH_SKILL_SRC      = RESOURCES_DIR / "agent-clis" / "claude" / "sdd-orchestrator" / "SKILL.md"
CLAUDE_ORCH_SKILL_TARGET_DIR = Path(".claude/skills/sdd-orchestrator")

def write_with_backup(target: Path, content: str) -> None  # extracted from the duplicated OpenCode backup blocks; diff→backup/conflict→write
def _compose_agent_body(src: Path, home: Path) -> str       # fm + optional shared prompt + {{HOME}} sub
```
`write_with_backup` is a deep helper hiding the diff/backup/conflict ritual currently inlined 3× — extracting it reduces, not adds, surface. Uninstall mirrors the OpenCode loop: remove a Claude file only when its content still equals the composed install output, then restore `<name>.ai-harness-backup`; never auto-restore conflict backups; enumerate agent removal by `CLAUDE_AGENTS_SRC.iterdir()` (like `project_skill_names`).

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | compose join == shared prompt verbatim; inline files pass through; `{{HOME}}` sub; backup/conflict/uninstall content-match | pytest on `tmp_path` home |
| E2E | install stages 15 agents + skill; uninstall restores; idempotent re-install | `e2e/docker-test.sh` (red-first) |

## Migration / Rollout

No data migration. Additive; OpenCode wiring + shared prompts untouched. Rollback: delete `resources/agent-clis/claude/`, new constants, and the Claude install/uninstall blocks.

## Open Questions

None blocking. Residual for `sdd-tasks`: implementation is large (15 authored agent files + helper extraction + tests) — slice to stay within the 400-line review budget. `inherit` choices for apply/jd-fix assume the user runs SDD on a capable tier.
