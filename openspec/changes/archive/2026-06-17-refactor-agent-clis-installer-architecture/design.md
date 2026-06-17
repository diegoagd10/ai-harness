# Design: Refactor Agent-CLIs Installer Architecture

## Goals

- Eliminate duplicated prompt bodies across `claude/agents/`, `copilot-cli/agents/`, and `opencode.json`.
- Each logical agent body has exactly one canonical file under `resources/prompts/<namespace>/`.
- Installers own metadata (name, description, tools, model) as embedded Python data.
- All artifacts generated in memory; `agent-clis/<provider>/` becomes write-only e2e shim.
- Byte-equivalent install output; all existing tests pass unchanged.

## Module Layout

| File | Action | Responsibility |
|------|--------|----------------|
| `resources/prompts/jd/jd-{fix-agent,judge-a,judge-b}.md` | Create | Canonical bodies for judgment-day agents (3 files) |
| `resources/prompts/review/review-{risk,readability,reliability,resilience}.md` | Create | Canonical bodies for review agents (4 files) |
| `resources/prompts/orchestrator/sdd-orchestrator-agent.md` | Create | Claude Agent-tool orchestrator body |
| `resources/agent-clis/claude/agents/{jd,review}-*.md` | Modify | Strip bodies; frontmatter-only (7 files) |
| `resources/agent-clis/copilot-cli/agents/{jd,review}-*.md` | Modify | Strip bodies; frontmatter-only (7 files) |
| `resources/agent-clis/opencode/opencode.json` | Modify | Inline `prompt` strings → `{file:{{HOME}}/...}` references |
| `artifacts/installers/claude.py` | Modify | Embed metadata; inline agents → composed; add shim writes |
| `artifacts/installers/copilot.py` | Modify | Same pattern; hook JSON stays file-sourced |
| `artifacts/installers/opencode.py` | Modify | Extend prompt copy to `jd/`, `review/`, `orchestrator/` dirs |
| `artifacts/catalog.py` | Modify | Add path constants for new prompt subdirs |
| `artifacts/manifest.py` | Modify | Add `frontmatter_text` field to `ComposedFileArtifact` |
| `artifacts/installer.py` | Modify | Handle `frontmatter_text` in `_prepare_composed_content` |

## Public Interfaces (new/modified)

```python
# manifest.py — field addition to ComposedFileArtifact
@dataclass(frozen=True)
class ComposedFileArtifact:
    frontmatter_source: Path | None = None  # existing
    frontmatter_text: str | None = None     # NEW: alternative to file source
    body_source: Path
    target_relative: Path
    template: dict[str, str] = field(default_factory=dict)
    backup_suffix: str = ".ai-harness-backup"
    conflict_suffix: str = ".ai-harness-conflict-backup"

# catalog.py — new path constants
JD_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "jd"
REVIEW_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "review"
ORCHESTRATOR_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "orchestrator"

# Each installer embeds a _METADATA dict:
#   { "agent-id": {"name": str, "description": str, "tools": list[str],
#                   "model": str, ...} }
# Used to compose artifacts without reading agent-clis/ as a source.
```

## Data Flow

```
PromptStore (prompts/<ns>/<name>.md)          Installer._METADATA (embedded dict)
        │                                              │
        ▼                                              ▼
     body text                                   frontmatter text
        │                                              │
        └──────────────┬───────────────────────────────┘
                       ▼
              ComposedFileArtifact(frontmatter_text, body_source)
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   install target   shim path      (ComposedFileArtifact route)
   (~/.claude/...)  (agent-clis/)  via generic installer
          │            │
          ▼            ▼
   E2e asserts installed == shim (byte-equivalent)
```

For OpenCode: canonical prompt files → copied to `~/.config/opencode/prompts/<ns>/`.
`opencode.json` references them via `{file:{{HOME}}/...}`; `{{HOME}}` template
substitution resolves at install time. No in-memory JSON generation needed.

## Architecture Decisions

### Decision: Orchestrator Body

**Choice**: Two separate canonical files — `prompts/sdd/sdd-orchestrator.md` (task
variant, existing) + `prompts/orchestrator/sdd-orchestrator-agent.md` (Agent
variant, new).

**Alternatives**: (a) One file with `{{DELEGATION_TOOL}}` substitution.

**Rationale**: The bodies differ in tool name references and delegation semantics,
not just a single token swap. Two files are simpler to read, test, and maintain
than a templating convention. Claude's SKILL.md body already exists; extracting it
into a canonical file is a copy, not a rewrite. No template engine needed.

### Decision: Canonical Prompt Path

**Choice**: `resources/prompts/<namespace>/<name>.md`. Namespaces: `sdd/` (existing),
`jd/`, `review/`, `orchestrator/`.

**Rationale**: Consistent with existing `prompts/sdd/` convention. No flat namespace
collisions. Each body lives exactly once — grep finds it immediately.

### Decision: E2e Shim Path

**Choice**: Same as legacy: `agent-clis/claude/agents/`, `agent-clis/copilot-cli/agents/`,
`agent-clis/opencode/opencode.json`. Installers write composed output there.

**Rationale**: E2e constants (`CLAUDE_AGENTS_SRC`, `COPILOT_AGENTS_SRC`,
`OPENCODE_JSON_SRC`) resolve unchanged. E2e tests compare shim ↔ installed file;
both are deterministic composed output → byte-identical.

## Idempotency Strategy

**Technique**: Deterministic composition + whole-file write. The composition
function (`frontmatter_text.rstrip("\n") + "\n---\n" + body`) is pure and
non-accumulative. The generic installer writes entire file on every install,
comparing pre/post content — no append, no merge drift. N consecutive installs
produce byte-identical artifacts.

## Copilot 30K Budget

Budget applies to composed output (frontmatter + body). Moving body to canonical
source changes nothing — frontmatter is identical, body is identical. The
`_validate_composed_budget` method and its e2e counterpart continue to operate on
the same composed content.

## Migration Plan (order of operations)

1. **Add canonical prompt files**: `prompts/jd/*.md`, `prompts/review/*.md`,
   `prompts/orchestrator/sdd-orchestrator-agent.md`. Verify `pytest` green (no-op).
2. **Add `frontmatter_text` to manifest + installer**: `ComposedFileArtifact`
   field + `_prepare_composed_content` branch. Green.
3. **Embed metadata in ClaudeInstaller**: `_METADATA` dict, switch `_INLINE_AGENTS`
   from `FileArtifact` to `ComposedFileArtifact(frontmatter_text=..., body_source=...)`.
   Add shim write step. Green.
4. **Strip bodies from Claude agent-clis files**: `jd-*.md`, `review-*.md` →
   frontmatter-only. Green.
5. **Repeat 3–4 for CopilotInstaller**. Green.
6. **Update opencode.json**: inline prompts → `{file:...}` references. Extend
   OpencodeInstaller prompt copy to `jd/`, `review/`, `orchestrator/`. Green.
7. **Delete redundant output**: none needed — old `agent-clis/` files already
   stripped in steps 4–5, opencode.json inline strings replaced in step 6.
8. **Run full e2e**: `e2e/docker-test.sh`. Green.

Every step keeps `uv run pytest` green (unit) and e2e green from step 8 onward.

## Test Plan (TDD-first)

| Order | Test file | What it pins |
|-------|-----------|--------------|
| 1 | `tests/test_manifest.py` | `ComposedFileArtifact` accepts `frontmatter_text`; `_prepare_composed_content` uses it |
| 2 | `tests/test_claude_installer.py` | Metadata-driven compose produces byte-identical output to old verbatim copy |
| 3 | `tests/test_copilot_installer.py` | Same; hook JSON untouched |
| 4 | `tests/test_install.py` | Canonical prompts copied to opencode prompts dir; opencode.json `{file:}` references resolve |
| 5 | `e2e/test_harness_lifecycle.py` | (no edit — green gate) |
| 6 | `e2e/test_copilot_cli_lifecycle.py` | (no edit — green gate) |

## Open Risks

- **800-line budget**: Estimated ~240 new lines (8 prompt files + manifest extension
  + installer metadata + logic). Within budget. If Copilot hook generation is pulled
  into scope (not planned), it would push close to the limit.
- **OpenCode sdd-init/sdd-onboard**: `opencode.json` has agent entries for
  `sdd-init` and `sdd-onboard` in the orchestrator permission allowlist but no
  corresponding agent block. Not addressed by this refactor — pre-existing.
- **`agent-clis/` shim persistence**: Shims are written on install, removed on
  uninstall (per spec). If install fails mid-way, shims may be partial. The generic
  installer's short-circuit-on-first-error behavior already handles this.
