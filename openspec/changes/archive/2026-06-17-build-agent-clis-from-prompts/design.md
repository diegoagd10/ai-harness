# Design: Build Agent CLIs from Prompts

## Goals

- Delete `agent-clis/` (37 files). Every artifact built in memory from `prompts/` + `_METADATA`.
- No reads from, no writes to `agent-clis/`. User-facing paths only.
- E2e constants retargeted to `resources/generated/`. E2e logic frozen.
- Installers write guarded fixtures; read-only source tree → silent skip.

## Module Layout

| File | Action | Responsibility |
|------|--------|----------------|
| `artifacts/installers/opencode.py` | Modify | Build `opencode.json` in memory; `_METADATA` per agent; drop `OPENCODE_JSON_SRC` |
| `artifacts/installers/claude.py` | Modify | Extend `_METADATA` to all 15 agents (8 SDD + 7 inline); compose from `frontmatter_text`; drop `agents_dir/orchestrator_dir` from `ClaudeAssets` |
| `artifacts/installers/copilot.py` | Modify | Extend `_METADATA` to all 16 agents; generate hook JSON in code; drop `agents_dir/hooks_dir` from `CopilotAssets` |
| `artifacts/catalog.py` | Modify | Remove `OPENCODE_JSON_SRC` constant |
| `artifacts/manifest.py` | Modify | Make `frontmatter_source` optional; `frontmatter_text` required for composed |
| `artifacts/installer.py` | Modify | Simplify `_prepare_composed_content` — drop `frontmatter_source` fallback |
| `resources/agent-clis/` | **Delete** | Entire directory tree removed |
| `resources/generated/.gitkeep` | Create | Git tracks the directory; `.gitignore` blocks generated content |
| `.gitignore` | Modify | Add `src/ai_harness/resources/generated/` (content, not the dir) |
| `e2e/test_harness_lifecycle.py` | Modify | 3 path constants retargeted |
| `e2e/test_copilot_cli_lifecycle.py` | Modify | 2 path constants retargeted |

All shim methods (`_write_shim`/`_write_shims`) become `_write_fixtures` — destination is `resources/generated/<provider>/`, guarded by `os.access(os.W_OK)`.

## Public Interfaces

```python
# catalog.py — DELETE line 19
# OPENCODE_JSON_SRC = ...  # removed

# manifest.py — frontmatter_source becomes optional
@dataclass(frozen=True)
class ComposedFileArtifact:
    frontmatter_text: str                      # required (was optional)
    body_source: Path
    target_relative: Path
    frontmatter_source: Path | None = None     # kept for future use; never set by v2
    # ... rest unchanged

# Each installer extends _METADATA to cover all agents:
#   Claude: 8 SDD phase entries added (name, description, tools, model)
#   Copilot: 9 SDD phase+orchestrator entries added
#   OpenCode: full agent config dict per entry for opencode.json assembly

# Claude/Copilot — shared helper module-level:
_DENY_PATHS: list[str] = [
    "~/.ssh/**", "~/.aws/**", "~/.gnupg/**",
    "~/.zshrc", "~/.bashrc", "~/.bash_history", "~/.zsh_history",
    "~/.netrc", "~/.config/gh/**", "~/.docker/config.json",
    "/tmp/**", "/etc/**", "/proc/**", "/sys/**", "/var/**",
]
```

## Data Flow

```
prompts/<ns>/<name>.md        _METADATA[agent_id]          provider glue
       │                            │                           │
       ▼                            ▼                           ▼
  body_bytes                   frontmatter_text           _DENY_PATHS, allowlist
       │                            │                           │
       └──────────┬─────────────────┴───────────────┬───────────┘
                  ▼                                 ▼
        ComposedFileArtifact                  opencode.json dict
        │ (Claude, Copilot)                   hook JSON dict (Copilot)
        │                                         │
   ┌────┴───────────────────┐                     │
   ▼                        ▼                     ▼
user-facing             resources/generated/     user-facing
~/.claude/agents/        <provider>/<path>        ~/.copilot/hooks/
~/.copilot/agents/       (guarded write)          ~/.config/opencode/
~/.config/opencode/
```

## Architecture Decisions

### Decision: opencode/blocks + opencode/plugins

**Choice**: Delete with the rest of `agent-clis/`.

**Rationale**: No Python code imports or installs them (grep confirmed zero references). No Claude/Copilot analogue. The spec requires `agent-clis/` MUST NOT exist — partial preservation is impossible. If needed later, restore from git history.

### Decision: copilot-cli/hooks

**Choice**: Build from code. Shared `_DENY_PATHS` constant.

**Rationale**: Hook JSON is purely deterministic — 15-agent allowlist + 5 tool deny blocks with identical path lists. Code-gen eliminates desync risk with OpenCode `permission.external_directory`. The deny paths are already duplicated across 5 tool blocks in the static file; a constant makes the single source of truth explicit. No data lives in the hook that the installer doesn't know.

### Decision: Generated fixture path

**Choice**: `src/ai_harness/resources/generated/`.

**Alternatives**: `build/` (outside package tree), no fixtures (e2e reads installed paths).

**Rationale**: Within `RESOURCES_DIR`, discoverable by catalog, tested by e2e constants. Gitignored so committed content stays clean. The installer writes `generated/<provider>/<path>` on install when the source tree is writable; e2e reads from generated paths after install.

## Build-from-Code Contract

- **Markdown (Claude/Copilot)**: `frontmatter_text.rstrip("\n") + "\n---\n" + body_bytes` — identical to current `_prepare_composed_content`. `frontmatter_text` comes from `_metadata_to_frontmatter()`; `body_bytes` from `prompts/<ns>/<name>.md`.
- **opencode.json**: `json.dumps(config_dict, indent=2)` — no file read. `config_dict` assembled from `_METADATA` entries (agent blocks, model allowances, permissions, prompts with `{file:{{HOME}}/...}` refs). `{{HOME}}` substitution by generic installer template.
- **Copilot hook**: `json.dumps(hook_dict, indent=2)` — `hook_dict` built from `_ALL_SUBAGENT_NAMES` and `_DENY_PATHS`.

## Idempotency Strategy

Same as v1: deterministic composition + whole-file write. `_prepare_composed_content` is pure. Generic installer compares pre/post content; writes only on change. N consecutive installs produce byte-identical artifacts.

## Read-Only Safety

Before writing fixtures, each installer checks `os.access(generated_dir, os.W_OK)`. If `False`, the install succeeds silently — no fixtures written, no error raised. This handles production installs from read-only packages (pip, uv) and CI environments with immutable source trees.

## Migration Plan

1. Add `_METADATA` entries for all agents in all three installers. `pytest` green (no-op — not yet wired).
2. Make `frontmatter_text` required in `ComposedFileArtifact`; drop `frontmatter_source` fallback in `_prepare_composed_content`. Green.
3. Switch SDD phase agents in Claude/Copilot to `frontmatter_text` from metadata (like inline agents already do). Green.
4. Build `opencode.json` in memory, generate Copilot hook in code. Green.
5. Add `_write_fixtures` methods guarded by `os.access(os.W_OK)`. Green.
6. Retarget 5 e2e constants to `resources/generated/`. Green.
7. Delete `agent-clis/` entirely. Green.
8. Remove `OPENCODE_JSON_SRC` from catalog. Green.
9. Update test assertions to verify `agent-clis/` absent, fixtures present, build-from-code determinism. Green.
10. Run `e2e/docker-test.sh`. Green.

## Test Plan (TDD-first)

| Order | Test file | What it pins |
|-------|-----------|--------------|
| 1 | `tests/test_manifest.py` | `frontmatter_source` optional; `frontmatter_text` required for composed |
| 2 | `tests/test_claude_installer.py` | All 15 agents use `frontmatter_text`; SDD phases use metadata; no `agent-clis/` reads; fixtures at `generated/claude/` |
| 3 | `tests/test_copilot_installer.py` | All 16 agents use `frontmatter_text`; hook built from code; fixtures at `generated/copilot-cli/` |
| 4 | `tests/test_install.py` | `opencode.json` built from metadata; `{file:}` refs resolve; no `OPENCODE_JSON_SRC` import |
| 5 | `tests/test_catalog.py` | `OPENCODE_JSON_SRC` absent; `get_resource_dir` example updated |
| 6 | `tests/test_prompt_inventory.py` | `test_no_byte_identical_copy_in_agent_clis` removed; `agent-clis/` absence asserted |
| 7 | `e2e/test_harness_lifecycle.py` | Constant-only retarget; assertions unchanged |
| 8 | `e2e/test_copilot_cli_lifecycle.py` | Constant-only retarget; assertions unchanged |

## Open Risks

- **OpenCode `sdd-init`/`sdd-onboard`**: Pre-existing orphan entries in opencode.json allowlist. Not addressed — out of scope.
- **Test fixtures with `agent-clis/` paths**: `test_claude_installer.py` and `test_copilot_installer.py` `_make_catalog_root` helpers create `agent-clis/` dirs in temp paths. These get rewritten — not a risk, just accounted for.
- **`COPILOT_HOOKS_SRC` never read by e2e logic**: The constant exists for resolution but no assertion uses it as a source. Retargeting it to `generated/copilot-cli/hooks/sdd-pre-tool-use.json` is safe.
- **opencode.json encoding in v1 `_write_shim`**: The current shim writes the HOME-substituted content (with corrupted `/tmp/pytest-of-...` paths) back to source. Deleting `agent-clis/` eliminates this problem completely.
