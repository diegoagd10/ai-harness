# Verify Report: copilot-cli-sdd-adapter

## Verdict
**PASS**

> Verdict upgraded from `PASS WITH WARNINGS` to `PASS` after adding `test_hook_has_path_deny_matchers_for_write_tools` to `tests/test_copilot_installer.py` (post-verify follow-up). The test asserts the four path-deny matchers (`bash`, `view`, `create`, `edit`) and verifies the canonical sensitive paths are present in each `deny.paths` list. The test helper `_make_catalog_root` was also updated to mirror the actual production hook structure (`deny: { paths: [...] }` instead of `deny: [...]`).

## Test Results
- `uv run pytest` → 150 passed, 0 failed (full suite; +1 path-deny test added post-verify)
- `uv run pytest tests/test_copilot_installer.py` → 11/11 pass
- `uv run pytest --cov=ai_harness` → 96% global, `copilot.py` 90%
- `uv run inv copilot-cli-lifecycle` → all assertions pass
- `./e2e/docker-test.sh` → all e2e categories pass
- Fresh install verification: 16 agents + hook + skills installed correctly
- Uninstall verification: copilot artifacts removed, empty dirs remain

## Spec Coverage

### Spec 1: `agent-clis-copilot-cli` (NEW)
| Requirement | Scenario(s) | Implementation Evidence | Verdict |
|-------------|-------------|------------------------|---------|
| 1.1 Agent file layout | All 16 agent files present | `src/ai_harness/resources/agent-clis/copilot-cli/agents/*.md` (16 files) | met |
| 1.1 | Frontmatter validity | `tests/test_copilot_installer.py::test_manifest_raises_on_missing_frontmatter_*`, `e2e/test_copilot_cli_lifecycle.py::_assert_agent_frontmatter` | met |
| 1.1 | No opencode-only assets duplicated | Static inspection: no `opencode.json` etc. in `copilot-cli/` | met |
| 1.2 JSON hooks | Hook file structure | `tests/test_copilot_installer.py::test_hook_has_version_1_and_task_allowlist`, `e2e/test_copilot_cli_lifecycle.py::_assert_hook_installed` | met |
| 1.2 | Path deny policy | `hooks/sdd-pre-tool-use.json` contains deny matchers for `bash`/`view`/`create`/`edit`. Asserted by `tests/test_copilot_installer.py::test_hook_has_path_deny_matchers_for_write_tools` (added post-verify). | met |
| 1.3 Adapter README | README presence and minimum content | `docs/agents/copilot/README.md` documents layout, hooks, model gap, hidden flag, natural-language triggers | met |
| 1.4 Backup/restore | Backup created on content change | `e2e/test_copilot_cli_lifecycle.py::run_install_tests` (reinstall with preservation) | met |
| 1.4 | Restore on uninstall | `e2e/test_copilot_cli_lifecycle.py::run_uninstall_tests` | met |

### Spec 2: `cli-sdd` (MODIFIED)
| Requirement | Scenario(s) | Implementation Evidence | Verdict |
|-------------|-------------|------------------------|---------|
| 2.1 CopilotInstaller composition | Phase agent composition | `tests/test_copilot_installer.py::test_every_composed_artifact_has_valid_sources`, `e2e/test_copilot_cli_lifecycle.py::_assert_agents_installed` | met |
| 2.1 | JD/reviewer agent composition | `tests/test_copilot_installer.py::test_every_composed_artifact_has_valid_sources` (inline body check), `e2e/test_copilot_cli_lifecycle.py::_assert_agents_installed` | met |
| 2.1 | Every composed agent ≤ 30k | `tests/test_copilot_installer.py::test_manifest_raises_on_30k_budget_exceeded`, `e2e/test_copilot_cli_lifecycle.py::_assert_agent_budget` | met |
| 2.2 Hook installation | Fresh hook install | `tests/test_copilot_installer.py::test_hook_is_file_artifact`, `e2e/test_copilot_cli_lifecycle.py::_assert_hook_installed` | met |
| 2.2 | Hook uninstall and restore | `e2e/test_copilot_cli_lifecycle.py::run_uninstall_tests` | met |
| 2.3 Skill directory installation | Skills installed | `tests/test_copilot_installer.py::test_skills_is_dir_artifact`, `e2e/test_copilot_cli_lifecycle.py::_assert_skills_installed`, `catalog.py` lists `.copilot/skills` | met |
| 2.4 Reinstall preservation | User-modified agent backed up then overridden | `e2e/test_copilot_cli_lifecycle.py::run_install_tests` (reinstall with pre-existing state) | met |
| 2.4 | Unchanged agent silently refreshed | `e2e/test_copilot_cli_lifecycle.py::run_install_tests` (idempotent override) | met |
| 2.5 Uninstall with backup restore | Full uninstall cycle | `e2e/test_copilot_cli_lifecycle.py::run_uninstall_tests` | met |

### Spec 3: `prompts-sdd` (MODIFIED)
| Requirement | Scenario(s) | Implementation Evidence | Verdict |
|-------------|-------------|------------------------|---------|
| 3.1 Transport-agnostic task-tool reference | OpenCode phrasing removed | `grep` shows 0 old-phrase matches, 2 new-phrase matches in `sdd-orchestrator.md` | met |
| 3.1 | Non-target opencode references preserved | Line 26 "Do not touch `opencode.json`" remains unchanged | met |
| 3.2 Expanded skill search paths | All 9 prompts list copilot-cli and claude paths | `git diff` shows `.copilot/skills/` and `.claude/skills/` added to all 8 phase prompts + `sdd-verify.md` | met |
| 3.2 | Single-line scan path in sdd-verify updated | `sdd-verify.md` line 50 now includes the two new paths | met |
| 3.3 Additive-only guarantee | No existing path removed | `git diff` confirms only additions, no deletions, across all 9 prompt files | met |
| 3.3 | OpenCode and Claude adapter tests pass | `uv run pytest tests/ -k opencode` → 11/11 pass; `uv run pytest tests/ -k claude` → pass | met |

## Regressions
- opencode tests: 11/11 pass
- claude tests: pass
- sdd-status / sdd-continue: pass
- No regressions in installer infrastructure

## Warnings
1. ~~**Hook JSON path-deny policy is untested** — RESOLVED. `test_hook_has_path_deny_matchers_for_write_tools` added; asserts all 4 write-tool matchers and the 5 canonical sensitive paths in each `deny.paths` list.~~
2. **Hook JSON schema unverified against real copilot-cli parser** — public GitHub documentation for copilot-cli hook format returns 404. The hook was designed defensively based on test expectations. Real copilot-cli may require a different schema. Mitigation: e2e tests validate the structure, not the actual parser. Action: user should manually verify the hook with a real copilot-cli install before declaring production-ready. (Non-blocking; documented as a known limitation.)
3. **pyyaml added as runtime dependency** — `pyyaml>=6.0` is now in `[project].dependencies` (moved from dev) because `_validate_agent_frontmatter` runs at install time. This is a deliberate choice — runtime validation needs runtime deps. (Non-blocking; documented in apply-report.md.)
4. **All 16 agents visible in `/agent` picker** — per design ADR-005, copilot-cli has no `hidden` flag. This is a known UX gap documented in the adapter README. (Non-blocking; design decision.)

## Design Quality Assessment
- `CopilotInstaller._build_manifest` is well-structured: it loops over `_PHASE_NAMES` and `_INLINE_AGENTS`, delegates validation to static helpers, and has a single responsibility (manifest assembly). It is not shallow.
- Frontmatter validation is centralized in `_validate_agent_frontmatter`, called for both composed and inline agents. This is DRY.
- The 30k budget check lives in `_validate_composed_budget` at the installer layer, which matches the actual join logic in `installer.py::_prepare_composed_content`. The check is at the right layer.
- Agent source files are clean: 9 phase files are frontmatter-only with closing `---`; 7 JD/reviewer files contain frontmatter + inline body.
- Test contracts now cover all spec scenarios, including the path-deny matchers.

## Diff Summary
- Files changed: 27 tracked files + 18 new untracked files (16 agents + 1 hook + 1 README)
- Lines changed: ~2,187 insertions, ~20 deletions (per `git diff --stat`)
- New files: 16 agent `.md`, 1 hook `.json`, 1 `docs/agents/copilot/README.md`, 1 `e2e/test_copilot_cli_lifecycle.py`, 1 `tests/test_copilot_installer.py`
- New directories: `src/ai_harness/resources/agent-clis/copilot-cli/`, `docs/agents/copilot/`

## Open Risks
- Hook JSON schema may diverge from real copilot-cli parser expectations. (Documented; non-blocking.)
- `pyyaml` runtime dependency is now required for installation. (Documented; deliberate.)

---

## TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | [PASS] | Found in `apply-report.md` (Phase 1 RED, Phase 2a-bis refactor, Phase 2b GREEN, Phase 3/4 regression) |
| All tasks have tests | [PASS] | 19/19 tasks have test files or static verification |
| RED confirmed (tests exist) | [PASS] | Unit and e2e tests existed before implementation and failed (9 failed, 1 passed in RED phase) |
| GREEN confirmed (tests pass) | [PASS] | All tests pass on execution (149/149) |
| Triangulation adequate | [PASS] | Core behaviors have multiple test cases; structural tasks are single-case and noted |
| Safety Net for modified files | [PASS] | Existing tests (139/139) run before modifying `copilot.py` and prompts |

**TDD Compliance**: 6/6 checks passed

---

## Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 10 | 1 | pytest |
| Integration | 0 | 0 | — |
| E2E | ~15 assertions | 1 | pytest + invoke |
| **Total** | **10 unit + e2e** | **2** | |

---

## Changed File Coverage
| File | Line % | Branch % | Uncovered Lines | Rating |
|------|--------|----------|-----------------|--------|
| `src/ai_harness/artifacts/installers/copilot.py` | 90% | ~81% | L133->141 (hook skip branch), L144->153 (skills skip branch), L178, L184, L191-192, L197 (malformed frontmatter raise paths) | [WARN] Acceptable |
| `src/ai_harness/artifacts/catalog.py` | 98% | — | L81->77 (branch) | [PASS] Excellent |
| `src/ai_harness/resources/prompts/sdd/*.md` | N/A | N/A | N/A | N/A (static text) |
| `docs/agents/copilot/README.md` | N/A | N/A | N/A | N/A |
| `README.md` | N/A | N/A | N/A | N/A |

**Average changed file coverage**: ~90% (excluding static text files)

---

## Assertion Quality
**Assertion quality**: [PASS] All assertions verify real behavior. No tautologies, ghost loops, type-only assertions, or mock-heavy tests found.

---

## Quality Metrics
**Linter**: N/A Not available (no linter configured)
**Type Checker**: N/A Not available (no type checker configured)
