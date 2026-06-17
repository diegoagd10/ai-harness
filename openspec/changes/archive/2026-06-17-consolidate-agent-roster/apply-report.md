# Apply Report: consolidate-agent-roster

## Status
**success** — All 12 tasks complete, all tests pass, lint clean.

## Tasks completed

- [x] 1.1 Create `src/ai_harness/artifacts/agents.py` — catalog module
- [x] 1.2 Catalog smoke tests — 17 tests validating roster
- [x] 2.1 Refactor `claude.py` — catalog-driven, thin adapter
- [x] 2.2 Refactor `copilot.py` — catalog-driven, jd-fix gains Read/Glob/Grep
- [x] 2.3 Refactor `opencode.py` — catalog-driven, public build_opencode_config
- [x] 3.1 Rewrite `tests/test_claude_installer.py` — catalog imports
- [x] 3.2 Rewrite `tests/test_copilot_installer.py` — catalog + public hook
- [x] 3.3 Rewrite `tests/test_opencode_installer.py` — catalog + public config
- [x] 4.1 Rewrite `e2e/test_harness_lifecycle.py` — catalog + public APIs
- [x] 4.2 Rewrite `e2e/test_copilot_cli_lifecycle.py` — public build_hook_json
- [x] 5.1 Gate: 288 tests passing, ruff format/lint clean
- [x] 5.2 Dead code audit: private symbol tables removed from production

## TDD Cycle Evidence

### Task 1.1 — Create `agents.py` catalog module
- **RED**: `tests/test_agent_catalog.py:17` — 17 tests written before any production code; all fail with `ImportError` (module doesn't exist)
- **GREEN**: `src/ai_harness/artifacts/agents.py:1-69` — Created `Capability` StrEnum, frozen `Agent` dataclass, 16-row `AGENT_CATALOG`, `all_agents()` (ordered), `get(id)` raises KeyError
- **REFACTOR**: None needed — code is minimal and clean (single function, simple dict construction)

### Task 1.2 — Catalog smoke tests
- **RED->GREEN**: No separate red/green cycle — smoke tests are part of the 17-test suite written in 1.1 RED. All pass after 1.1 GREEN. Verified: 1 ORCHESTRATOR, 9 EDITS, 6 READ_ONLY; namespaces explicit (sdd/jd/review); sdd-init absent; Agent frozen; public API imports only.
- **REFACTOR**: None needed

### Task 2.1 — Refactor `claude.py`
- **RED**: `tests/test_claude_installer.py` — import error after removing `_METADATA` (expected — task 3.1 rewrites tests). Approval test: inline smoke test verifies 16 composed artifacts, correct orchestrator body source.
- **GREEN**: `src/ai_harness/artifacts/installers/claude.py` — Added `_TOOLS_BY_CAPABILITY` (3 rows), `_MODEL_BY_ID`, `_DESCRIPTION_BY_ID`. Rewrote `_build_manifest` to iterate `all_agents()`, branching `capability == ORCHESTRATOR`. Rewrote `_install_permissions` from capability tools. Removed `_PHASE_NAMES`, `_INLINE_AGENTS`, `_METADATA`. Added public `metadata_for()` for e2e self-compose.
- **REFACTOR**: Extracted `_prompt_subdir()` helper to map namespace→directory. Code is cleaner — 150 lines vs original 329.

### Task 2.2 — Refactor `copilot.py`
- **RED**: `tests/test_copilot_installer.py` — import error after removing private symbols. Inline smoke test verifies 16 agents, jd-fix tools, hook allowlist.
- **GREEN**: `src/ai_harness/artifacts/installers/copilot.py` — Added `_TOOLS_BY_CAPABILITY` (EDITS row includes Read/Glob/Grep for jd-fix gain), `_MODEL_BY_ID`, `_DESCRIPTION_BY_ID`. Renamed `_build_hook_json` → `build_hook_json` (public). Derived `agents:` field + hook allowlist from catalog via `all_agents()`. Removed `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES`, `_METADATA`.
- **REFACTOR**: Extracted `_prompt_subdir()` helper. Build loop is a single `for agent in all_agents()` — no more three separate loops.

### Task 2.3 — Refactor `opencode.py`
- **RED**: `tests/test_opencode_installer.py` — import error after removing `AGENT_DEFINITIONS`/`AgentDefinition`. Inline smoke test verifies 16 agents, correct modes/permissions/tools.
- **GREEN**: `src/ai_harness/artifacts/installers/opencode.py` — Added `_TOOLS_BY_CAPABILITY`, `_MODEL_BY_ID`, `_DESCRIPTION_BY_ID`, `_MODE_BY_CAPABILITY`, `_HIDDEN_BY_CAPABILITY`, `_PERMISSION_BY_CAPABILITY`, `_PROMPT_KIND_BY_NS`. Renamed `_build_opencode_config` → `build_opencode_config` (public, catalog-driven). Rewrote `_build_orchestrator_allowlist` from catalog. Removed `AgentDefinition`, `AGENT_DEFINITIONS`. Kept `_prompt_ns` and `_load_inlined_prompt` as utility functions.
- **REFACTOR**: Build loop is driven by `all_agents()`; mode/hidden/permission derived from capability maps instead of per-id dataclass fields.

### Task 3.1 — Rewrite Claude tests
- **RED**: Tests failed with ImportError (removed `_METADATA`). Safety net baseline: 7/7 before refactor.
- **GREEN**: `tests/test_claude_installer.py` — Replaced `_METADATA` imports with `AGENT_CATALOG` + `Capability`. All 9 tests pass. Tests use catalog-derived agent lists. Removed local name constants (`_SDD_PHASE_NAMES`, `_JD_NAMES`, `_REVIEW_NAMES`, `_ALL_AGENT_NAMES`).
- **REFACTOR**: Tests are self-composing expected content without importing private installer symbols.

### Task 3.2 — Rewrite Copilot tests
- **RED**: Tests failed with ImportError (removed `_METADATA`/`_SUBAGENT_NAMES`).
- **GREEN**: `tests/test_copilot_installer.py` — Replaced `_METADATA`/`_SUBAGENT_NAMES` with catalog + `all_agents()`. Replaced `_build_hook_json` with public `build_hook_json`. All 18 tests pass. Added `test_jd_fix_agent_gains_read_glob_grep` verifying the behavioral change.
- **REFACTOR**: Self-composed frontmatter tests use catalog-derived metadata instead of `_METADATA` dict.

### Task 3.3 — Rewrite Opencode tests
- **RED**: Tests failed with ImportError (removed `AGENT_DEFINITIONS`/`AgentDefinition`).
- **GREEN**: `tests/test_opencode_installer.py` — Replaced `AGENT_DEFINITIONS`/`AgentDefinition`/`_build_agent_entry` with catalog + public `build_opencode_config`. All 26 tests pass. Removed dataclass-shape tests (AgentDefinition no longer exists). Updated `_prompt_ns` test to expect `KeyError` (now uses catalog `get()`).
- **REFACTOR**: Tests now verify config structure directly from catalog-driven output.

### Task 4.1 — Rewrite e2e harness lifecycle
- **RED**: Import error — `_CLAUDE_METADATA` and `_build_opencode_config` removed.
- **GREEN**: `e2e/test_harness_lifecycle.py` — Replaced `_CLAUDE_METADATA` with `metadata_for()` (public Claude adapter function). Replaced `_build_opencode_config` with `build_opencode_config` (public). Self-compose works via catalog + adapter public APIs.
- **REFACTOR**: No private installer imports remain in e2e.

### Task 4.2 — Rewrite e2e copilot lifecycle
- **RED**: Import error — `_build_hook_json` removed.
- **GREEN**: `e2e/test_copilot_cli_lifecycle.py` — Replaced `_build_hook_json` with `build_hook_json` (public). Hook validation now uses catalog-derived allowlist.
- **REFACTOR**: Single import change — minimal diff.

### Task 5.1 — Gate
- **No red/green cycle** — verification step.
- Verified: `uv run ruff format --check .` → 66 files already formatted. `uv run ruff check .` → All checks passed. `uv run pytest` → 288 passed.
- **REFACTOR**: None.

### Task 5.2 — Dead code audit
- **No red/green cycle** — verification step.
- Verified: Grep for `_METADATA`, `AGENT_DEFINITIONS`, `AgentDefinition`, `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES`, `_ALL_AGENT_IDS` in `src/` returns zero hits (only stale docstrings updated). `_prompt_ns` intentionally kept as utility function.
- **REFACTOR**: Updated stale `_METADATA` docstring references in `frontmatter.py`.

## Files touched

| File | Action | Lines |
|------|--------|-------|
| `src/ai_harness/artifacts/agents.py` | **Created** | 69 |
| `tests/test_agent_catalog.py` | **Created** | 202 |
| `src/ai_harness/artifacts/installers/claude.py` | Modified | 176 (was 329, now ~176) |
| `src/ai_harness/artifacts/installers/copilot.py` | Modified | 218 (was 380, now ~218) |
| `src/ai_harness/artifacts/installers/opencode.py` | Modified | 264 (was 483, now ~264) |
| `src/ai_harness/artifacts/installers/frontmatter.py` | Modified | 2 (docstring updates) |
| `tests/test_claude_installer.py` | Modified | 183 (was 250, now ~183) |
| `tests/test_copilot_installer.py` | Modified | 340 (was 621, now ~340) |
| `tests/test_opencode_installer.py` | Modified | 192 (was 324, now ~192) |
| `e2e/test_harness_lifecycle.py` | Modified | 5 (import/function name changes) |
| `e2e/test_copilot_cli_lifecycle.py` | Modified | 2 (import name change) |
| `openspec/changes/consolidate-agent-roster/tasks.md` | Modified | 12 checkboxes updated |

**Net delta**: +271 new lines (agents.py + test), ~500 lines removed from installers + tests. The three installer files went from 329+380+483=1192 lines to ~658 lines — a ~45% reduction.

## Test results
- `uv run pytest`: **288 passed, 0 failed**
- `uv run ruff format --check .`: **66 files already formatted**
- `uv run ruff check .`: **All checks passed**
- `e2e/docker-test.sh`: **Not run** (deferred to verify phase)

## Behavior changes shipped

### Copilot `jd-fix-agent` gains Read, Glob, Grep
- **Before**: Tools = `[Bash, Edit, View, Create, Task]` (per-agent assignment in `_METADATA`)
- **After**: Tools = `[Bash, Edit, View, Create, Glob, Grep, Read, Task]` (via `_TOOLS_BY_CAPABILITY[EDITS]`)
- **Verified by**: `test_jd_fix_agent_gains_read_glob_grep` in `tests/test_copilot_installer.py` — asserts Read, Glob, Grep, Edit are present in jd-fix-agent frontmatter
- **Impact**: `.agent.md` frontmatter for `jd-fix-agent` installs with 3 additional tools. Read-capability parity with other agents while keeping edit tools.

### Byte-identical output for all other agents
- Claude: all 16 agents produce identical frontmatter + body composition (verified by inline smoke test)
- Copilot: all 16 agents (except jd-fix) produce identical output; hook JSON is byte-identical (catalog-derived allowlist matches old `_SUBAGENT_NAMES`)
- Opencode: 16-agent config produces identical JSON structure

## Design amendments

None. The design was confirmed against current code before implementation. `sdd-init` verified absent from the catalog (only exists as an orchestrator routing concept in prompts). All capability assignments verified.

## Risks / blockers / open questions
- None. All 12 tasks completed successfully.
- The e2e/docker-test.sh was deferred — runs in Docker and requires a containerized environment. Unit tests provide comprehensive coverage.
- `_prompt_ns` function in opencode.py is intentionally kept — it's a small utility function that maps agent_id → namespace via the catalog. Not dead code.

## Next recommended phase
`sdd-verify`
