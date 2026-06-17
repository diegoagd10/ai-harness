# Tasks: Match OpenCode installer output to `target-opencode.json`

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~280-360 (production 150-200 + tests 130-160) |
| 400-line budget risk | Low |
| 800-line budget risk | Low |
| Size exception needed | No |
| Suggested work units | Not needed (single-PR delivery) |
| Delivery strategy | single-pr |
| Size exception | No |

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Low

The change fits comfortably under both the 400-line default and the user-selected 800-line review budget. No work units or size exception required.

## Phase 1: Infrastructure

- [x] **1.1**: Define `AgentDefinition` frozen dataclass (8 fields: `agent_id`, `description`, `mode`, `hidden`, `model`, `permission`, `tools`, `prompt_kind`).
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run ruff check src/ai_harness/artifacts/installers/opencode.py`
  - TDD: not applicable (data shape; covered by 3.1-3.6 contract tests)
  - Estimate: S (~15 LOC)
  - Notes: Place above `_METADATA`/`AGENT_DEFINITIONS`. Fold `prompt_ns` (ADR-07) and drop `prompt_body_override` (ADR-08).

- [x] **1.2**: Add module-level constants `_SCHEMA_URL` and `_PERMISSION_BLOCK` (lift current permission dict from lines 239-251).
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run ruff check src/ai_harness/artifacts/installers/opencode.py`
  - TDD: not applicable (literal refactor; covered by 3.3 snapshot test)
  - Estimate: S (~30 LOC)
  - Notes: `_SCHEMA_URL = "https://opencode.ai/config.json"`. Keep `_DENY_PATHS`, `_ALL_AGENT_IDS`, `_SUBAGENT_NAMES` unchanged.

- [x] **1.3**: Implement `_prompt_ns(agent_id: str) -> str` helper (prefix → namespace, raises on unknown).
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run ruff check src/ai_harness/artifacts/installers/opencode.py`
  - TDD: RED — write `pytest.raises` test asserting unknown id fails; GREEN — implement prefix map; REFACTOR — tighten dispatch.
  - Estimate: S (~10 LOC)
  - Notes: Map `sdd-*` → `sdd`, `jd-*` → `jd`, `review-*` → `review`, orchestrator → `sdd`.

- [x] **1.4**: Implement `_load_inlined_prompt(prompts_root: Path, agent_id: str) -> str` helper (reads `.md` body verbatim).
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run pytest tests/test_install.py::test_inline_prompt_reflects_md_edit` (when test 3.4 lands)
  - TDD: RED — test asserts body matches disk after edit; GREEN — implement read; REFACTOR — single I/O site.
  - Estimate: S (~10 LOC)
  - Notes: ONLY I/O site for inlined prompts. ADR-01 single source of truth.

- [x] **1.5**: Implement `_build_orchestrator_allowlist() -> dict[str, str]` returning `{"*":"deny", <15 sub-agents>:"allow"}`.
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run pytest tests/test_install.py::test_orchestrator_allowlist_has_15_entries` (when test 3.5 lands)
  - TDD: RED — assert 15 entries, no `sdd-init`/`sdd-onboard`; GREEN — derive from `_SUBAGENT_NAMES` minus orphans; REFACTOR — clarify intent.
  - Estimate: S (~8 LOC)
  - Notes: ADR-03 drops `sdd-init`/`sdd-onboard`. Doc comment must call out the drop.

## Phase 2: Implementation

- [x] **2.1**: Replace `_METADATA` with `AGENT_DEFINITIONS: list[AgentDefinition]` (16 entries: orchestrator + 7 sdd sub-phases + 3 jd + 4 review). Inline kind for the 7 jd-/review-* agents; file_ref kind for the 9 sdd-* agents.
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run pytest tests/test_install.py::test_opencode_json_matches_target_reference` (when test 3.3 lands)
  - TDD: not applicable (data definition; covered by 3.1-3.6 contract tests)
  - Estimate: M (~80-100 LOC, the bulk of the production change)
  - Notes: Pin model per design §4 ADR-02 model map. Extend review-* descriptions verbatim. Add `permission: {"edit":"deny"}` to jd-judge-a/-b and 4 review-* (NOT jd-fix-agent per ADR-05).

- [x] **2.2**: Implement `_build_agent_entry(agent: AgentDefinition, prompt_body: str | None) -> dict` (compose one agent's JSON dict; emit `hidden`/`model`/`permission` only when set).
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run pytest tests/test_install.py::test_readonly_agents_deny_edit` (when test 3.6 lands)
  - TDD: RED — assert 6 read-only agents emit `permission.edit: "deny"` and `jd-fix-agent` does not; GREEN — implement dispatch; REFACTOR — one branch per field.
  - Estimate: S (~20 LOC)
  - Notes: Deep-modules rule: one decision per branch, no embedded data.

- [x] **2.3**: Rewrite `_build_opencode_config(catalog)` to: iterate `AGENT_DEFINITIONS`, call `_load_inlined_prompt` for inline kinds, build entries, then attach orchestrator `permission.task` from `_build_orchestrator_allowlist()`. Emit `$schema`, `_PERMISSION_BLOCK`, `agent`, `share: "disabled"`.
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run pytest tests/test_install.py::test_opencode_json_matches_target_reference` (when test 3.3 lands)
  - TDD: RED — snapshot test fails on current code; GREEN — this rewrite; REFACTOR — tighten shape.
  - Estimate: M (~20-30 LOC, slim per design §2)
  - Notes: Drop orphan `sdd-init`/`sdd-onboard` entries. Keep `_build_manifest` unchanged (template mechanism stays).

- [x] **2.4**: Verify model map matches design §6 ADR-02 (orchestrator=openai/gpt-5.5; apply/propose/spec/design/tasks=deepseek-v4-pro; explore=kimi-k2.7-code; archive=deepseek-v4-flash; verify=kimi-k2.6; jd-*/review-* have NO model).
  - Files: `src/ai_harness/artifacts/installers/opencode.py`
  - Verify: `uv run pytest tests/test_install.py::test_subphase_models_pinned` (new assertion inside existing 16-agent test)
  - TDD: RED — assert each model's exact value AND absence on jd-*/review-*; GREEN — model field already set in 2.1; REFACTOR — extract constants if needed.
  - Estimate: S (~5 LOC test)
  - Notes: Spec line `spec.md:88-96` is the contract.

## Phase 3: Testing

- [x] **3.1**: Split assertion at `tests/test_install.py:99-101` into two loops: `sdd-*` agents must use `{file:}` refs; 7 jd-*/review-* agents must have inlined non-empty strings (not starting with `{file:`).
  - Files: `tests/test_install.py`
  - Verify: `uv run pytest tests/test_install.py::test_install_copies_opencode_configuration`
  - TDD: RED — current universal assertion fails after 2.3; GREEN — split loops; REFACTOR — extract `SDD_IDS`/`INLINE_IDS` constants.
  - Estimate: S (~10 LOC delta)
  - Notes: Spec scenario "Metadata separated from prompt body" (`spec.md:18-24`).

- [x] **3.2**: Invert assertion at `tests/test_install.py:145-161`: those 7 agents have INLINED prompts (non-empty string, not a `{file:}` ref). Keep on-disk `.md` copy assertions at lines 124-143.
  - Files: `tests/test_install.py`
  - Verify: `uv run pytest tests/test_install.py::test_install_copies_jd_review_orchestrator_prompts`
  - TDD: RED — current `{file:}` assertion fails after 2.3; GREEN — invert; REFACTOR — assert body matches source `.md` verbatim.
  - Estimate: S (~10 LOC delta)
  - Notes: Spec scenario "Inlined prompts reflect on-disk .md at install time" (`spec.md:80-83`).

- [x] **3.3**: Add `test_opencode_json_matches_target_reference`: stub `$HOME`, run `install --all`, load generated JSON, load `reference/target-opencode.json` with `/home/diegoagd10` → `tmp_path` substitution, deep-compare via `json.dumps(..., indent=2, sort_keys=True)`.
  - Files: `tests/test_install.py`
  - Verify: `uv run pytest tests/test_install.py::test_opencode_json_matches_target_reference`
  - TDD: RED — must fail against current installer (7 known gaps); GREEN — install from 2.3 produces matching JSON; REFACTOR — tighten error messages.
  - Estimate: M (~40 LOC)
  - Notes: This is the regression net for ALL 7 gaps (ADR-06). Reference file lives at `openspec/changes/install-opencode-template/reference/target-opencode.json`.

- [x] **3.4**: Add `test_inline_prompt_reflects_md_edit`: edit `resources/prompts/review/review-risk.md`, re-install, assert the inlined `review-risk` prompt starts with `MUTATION_MARKER`. Use `try/finally` to restore the file even on assertion failure.
  - Files: `tests/test_install.py`
  - Verify: `uv run pytest tests/test_install.py::test_inline_prompt_reflects_md_edit`
  - TDD: RED — fails if installer bakes body at import; GREEN — proves read-at-install-time (ADR-01); REFACTOR — extract marker constant.
  - Estimate: S (~30 LOC)
  - Notes: Proves the ADR-01 invariant. NEVER run in parallel (file mutation).

- [x] **3.5**: Add `test_orchestrator_allowlist_has_15_entries`: assert `agent["sdd-orchestrator"]["permission"]["task"]` has 16 keys (15 sub-agents + `"*"`), and `sdd-init`/`sdd-onboard` are absent.
  - Files: `tests/test_install.py`
  - Verify: `uv run pytest tests/test_install.py::test_orchestrator_allowlist_has_15_entries`
  - TDD: RED — fails today (current code emits `sdd-init`/`sdd-onboard`); GREEN — after 2.3 drops orphans; REFACTOR — assert exact key set.
  - Estimate: S (~15 LOC)
  - Notes: ADR-03 contract. CHANGELOG must call out the drop.

- [x] **3.6**: Add `test_readonly_agents_deny_edit`: assert the 6 read-only agents (`jd-judge-a`, `jd-judge-b`, `review-readability`, `review-reliability`, `review-resilience`, `review-risk`) each emit `"permission": {"edit": "deny"}`, and `jd-fix-agent` does NOT carry a `permission` key.
  - Files: `tests/test_install.py`
  - Verify: `uv run pytest tests/test_install.py::test_readonly_agents_deny_edit`
  - TDD: RED — fails today (only 2 of 6 deny edit); GREEN — after 2.1 sets `permission` on review-*; REFACTOR — derive readonly set from a constant.
  - Estimate: S (~15 LOC)
  - Notes: ADR-05 documents `jd-fix-agent` asymmetry. Spec scenario `spec.md:113-117`.

## Phase 4: Validation & E2E

- [x] **4.1**: Run ruff format + ruff check; auto-fix safe issues if any.
  - Files: (validation only — no edits expected after fixes)
  - Verify: `uv run ruff format --check . && uv run ruff check .`
  - TDD: not applicable (formatting gate)
  - Estimate: S (1-2 min)
  - Notes: Must pass before tests per `openspec/config.yaml` validation hygiene.

- [x] **4.2**: Run full pytest suite — no regressions; all new tests green.
  - Files: (test run only)
  - Verify: `uv run pytest`
  - TDD: not applicable (full suite gate)
  - Estimate: S (3-5 min)
  - Notes: Existing tests at `tests/test_install.py:67+` and `test_uninstall.py` must still pass.

- [x] **4.3**: Run e2e docker test — exercises the installed `ai-harness` binary end-to-end and validates the generated `opencode.json` in a clean container.
  - Files: (e2e only)
  - Verify: `e2e/docker-test.sh`
  - TDD: not applicable (e2e gate)
  - Estimate: M (5-10 min, depends on docker)
  - Notes: This catches environment-specific issues (e.g. `$HOME` resolution on Linux, path templating).

- [x] **4.4**: Add CHANGELOG entry for dropped `sdd-init`/`sdd-onboard` allowlist entries and bump minor version in `pyproject.toml`.
  - Files: `openspec/CHANGELOG.md`, `pyproject.toml`
  - Verify: `grep -E "sdd-init|sdd-onboard" openspec/CHANGELOG.md` returns the new entry; `grep -E "^version" pyproject.toml` shows the bumped minor.
  - TDD: not applicable (documentation/release hygiene)
  - Estimate: S (~5 LOC)
  - Notes: ADR-03 contract. Tag the change as a breaking change for downstream consumers relying on those orchestrator tasks.

## Implementation Order

1. **Phase 1 first** (1.1-1.5): build the data shapes and helpers with TDD-driven red/green on each helper. Nothing else compiles without `AgentDefinition`.
2. **Phase 2 next** (2.1-2.4): define the 16-row data table, then rewrite `_build_opencode_config`. Phase 2.4 is a checkpoint (model map audit) before tests consume the config.
3. **Phase 3 last** (3.1-3.6): update the two existing assertion blocks (3.1, 3.2), then add the four new tests. Run `uv run pytest` after each new test lands so failures stay local.
4. **Phase 4 final** (4.1-4.4): formatting → unit tests → e2e → release hygiene. Phase 4.4 runs LAST because the CHANGELOG entry should describe the FINAL behavior.

The snapshot test (3.3) is the regression net for ALL 7 gaps. Until 3.3 is green, treat ANY 2.x task as incomplete.

## Review Workload Forecast (footer)

- Estimated changed lines: ~280-360 (production 150-200 + tests 130-160)
- 400-line budget risk: Low
- 800-line budget risk: Low
- Maintainer-approved size exception: No
- Delivery strategy: single-pr
- Decision needed before apply: No
- Suggested work units: Not needed

Decision needed before apply: No
Maintainer-approved size exception: No
400-line budget risk: Low