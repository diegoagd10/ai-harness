# Verify Report: consolidate-agent-roster

## Verdict
**PASS WITH WARNINGS**

## Test results (run during verify)
- `uv run pytest`: 288 passed, 0 failed
- `uv run ruff format --check .`: PASS (66 files already formatted)
- `uv run ruff check .`: PASS (All checks passed)

## A. Catalog correctness
- [x] `AGENT_CATALOG` has exactly 16 agents — `agents.py:54`, `test_agent_catalog.py:45-58`
- [x] Each row has `id`, `namespace`, `capability` only — `agents.py:21-25`, `test_agent_catalog.py:137-144`
- [x] `Capability` enum has exactly 3 members — `agents.py:15-18`, `test_agent_catalog.py:14-23`
- [x] `sdd-orchestrator` is the only ORCHESTRATOR; no `sdd-init` row — `agents.py:32`, `test_agent_catalog.py:73-85`
- [x] `Agent` is `@dataclass(frozen=True)` — `agents.py:21`, `test_agent_catalog.py:36-42`
- [x] Public surface is 5 symbols (`Capability`, `Agent`, `AGENT_CATALOG`, `all_agents()`, `get()`) — `agents.py:15-69`
- [x] `get(id)` raises `KeyError` on miss — `agents.py:67-69`, `test_agent_catalog.py:186-191`

## B. Adapter correctness

### claude.py
- [x] `_TOOLS_BY_CAPABILITY` has 3 rows — `claude.py:44-48`
- [x] No per-id tool list survives — grep for `tools=` keyed on agent id: none found
- [x] Per-id `model` and `description` tables survive — `claude.py:52-69`, `claude.py:73-101`
- [x] Build loop iterates `all_agents()` — `claude.py:215-237`
- [x] Public `install()`/`uninstall()` signatures preserved — `claude.py:149-181`

### copilot.py
- [x] `_TOOLS_BY_CAPABILITY` has 3 rows — `copilot.py:42-46`
- [x] No per-id tool list survives — grep for `tools=` keyed on agent id: none found
- [x] Per-id `model` and `description` tables survive — `copilot.py:74-113`
- [x] Build loop iterates `all_agents()` — `copilot.py:224-234`
- [x] Public `install()`/`uninstall()` signatures preserved — `copilot.py:189-197`

### opencode.py
- [x] `_TOOLS_BY_CAPABILITY` has 3 rows — `opencode.py:68-72`
- [x] No per-id tool list survives — grep for `tools=` keyed on agent id: none found
- [x] Per-id `model` and `description` tables survive — `opencode.py:94-144`
- [x] Build loop iterates `all_agents()` — `opencode.py:224-240`
- [x] Public `install()`/`uninstall()` signatures preserved — `opencode.py:280-290`

## C. Behavior change
- [x] Copilot `jd-fix-agent` has Read/Glob/Grep — `_TOOLS_BY_CAPABILITY[Capability.EDITS]` at `copilot.py:44`; verified by `test_copilot_installer.py:472-487`
- [x] Other agents byte-identical — spot-checks:
  - `sdd-explore` (EDITS): before `["Bash","Edit","View","Create","Glob","Grep","Read","Task"]` → after same via `_TOOLS_BY_CAPABILITY[EDITS]`
  - `review-risk` (READ_ONLY): before `["View","Bash","Glob","Grep","Task"]` → after same via `_TOOLS_BY_CAPABILITY[READ_ONLY]`
  - `sdd-orchestrator` (ORCHESTRATOR): before `["agent","Bash","Edit","View","Create","Glob","Grep","Read"]` → after same via `_TOOLS_BY_CAPABILITY[ORCHESTRATOR]`

## D. Untouched seam
- [x] `installer.py` unchanged — `git diff --stat HEAD -- src/ai_harness/artifacts/installer.py` returned empty
- [x] `ArtifactManifest` unchanged — `git diff --stat HEAD -- src/ai_harness/artifacts/manifest.py` returned empty

## E. Test surface
- [x] No private-symbol imports of `_METADATA`, `AGENT_DEFINITIONS`, `_PHASE_NAMES`, `_INLINE_AGENTS`, `_SUBAGENT_NAMES` in tests/ — grep returned only docstring references
- [x] Coverage of catalog, capability, adapter, e2e — 70 tests across 4 files; all pass
- [x] Triangulation + negative-path tests present:
  - Triangulation: `test_opencode_installer.py:40-55` (parametrize 8 agent ids), `test_opencode_installer.py:145-151` (3 agents per capability), `test_opencode_installer.py:154-159` (3 agents), `test_opencode_installer.py:169-184` (3+3 agents), `test_opencode_installer.py:197-211` (multiple agents per capability)
  - Negative paths: `test_agent_catalog.py:186-191` (KeyError on miss), `test_opencode_installer.py:58-61` (KeyError on unknown id), `test_copilot_installer.py:206-220` (budget exceeded ValueError), `test_opencode_installer.py:74-77` (FileNotFoundError)

## F. Lint and format
- [x] `uv run ruff format --check .` — PASS
- [x] `uv run ruff check .` — PASS

## G. TDD discipline
- [x] All 12 tasks have red/green/refactor traces in `apply-report.md` — documented for tasks 1.1 through 5.2
- [x] No "code first" anti-patterns — every task describes test-first or verification-first workflow

## H. Deep-modules audit
- [x] Catalog public surface is small (5 symbols) — `agents.py:15-69`; `_build_catalog()` is private
- [x] Adapters hide dialect tables — `_TOOLS_BY_CAPABILITY`, `_MODEL_BY_ID`, `_DESCRIPTION_BY_ID` are module-private in each adapter

## I. Out-of-scope check
- [x] No new agents added — still 16 rows in catalog
- [x] No description dedup — each adapter retains its own `_DESCRIPTION_BY_ID`
- [x] No model unification — each adapter retains its own `_MODEL_BY_ID`
- [x] `installer.py` / `ArtifactManifest` untouched — confirmed by git diff

## Warnings
1. **TDD evidence format deviation** — `apply-report.md` provides TDD Cycle Evidence in prose paragraphs rather than the mandated tabular format (`| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |`). The content is complete and auditable, but the format deviates from the `tdd-implement` skill protocol.
2. **Minor private-symbol imports in tests** — `tests/test_opencode_installer.py` imports `_prompt_ns` and `_load_inlined_prompt` (lines 15-19). These are small utility functions, not the large data tables that were the primary concern. The task explicitly says to keep `_load_inlined_prompt` tests, and `_prompt_ns` is documented as intentionally retained. This is a minor deviation from the ideal "no private imports" principle.
3. **`_build_agent_entry` not removed** — Task 2.3 says "Remove ... `_build_agent_entry`", but it remains in `opencode.py:184-213`. It is a harmless private helper used only by `build_opencode_config()`. No spec or behavior is broken, but the cleanup task was incomplete.
4. **Stale docstring references in e2e** — `e2e/test_harness_lifecycle.py:125-138` and `e2e/test_copilot_cli_lifecycle.py:178` still mention old private symbol names (`_METADATA`, `_build_hook_json`) in docstrings/comments. These are documentation drift, not functional imports.
5. **Unit-test coverage gap on install/uninstall paths** — `claude.py` install/uninstall methods are 60% covered by unit tests; `opencode.py` install/uninstall is 62%. The e2e suite covers these paths. This is a test-layer distribution observation, not a behavior gap.

## Failures
None.

## Recommendation
- `sdd-archive` — proceed. All hard requirements are satisfied. The warnings are non-blocking: format deviation, two kept utility imports, one uncleared helper, and stale docstrings.
