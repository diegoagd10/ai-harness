# Verify Report: install-opencode-template

**Change**: `install-opencode-template`
**Version**: 0.2.0
**Reviewer**: sdd-verify (independent re-verification)
**Execution mode**: Strict TDD verification (re-run all gates + walk every spec/ADR)
**Date**: 2026-06-17

---

## Final Verdict

**PASS** — every spec scenario covered, every ADR honored, all
tests/lint/e2e green, normalized deep-equal against the target reference
holds, no regressions, CHANGELOG and version bump in place.

---

## 1. Spec Coverage

Every scenario in `specs/agent-clis-installer/spec.md` was walked and
mapped to at least one passing test.

| # | Requirement / Scenario | Status | Evidence (file:line) |
|---|------------------------|--------|----------------------|
| 1 | Metadata separated from prompt body (`spec.md:18-24`) | [PASS] COMPLIANT | `tests/test_install.py:99-126` (split SDD_IDS / INLINE_IDS loops in `test_install_copies_opencode_configuration`); `tests/test_opencode_installer.py:404-411` (`test_build_opencode_config_sdd_agents_use_file_refs`); `:414-430` (`test_build_opencode_config_jd_review_inline_prompts`); `:432-450` (`test_build_opencode_config_jd_review_inline_matches_md_body`) |
| 2 | Top-level keys are exactly `$schema`, `permission`, `agent`, `share` (`spec.md:35-37`) | [PASS] COMPLIANT | `tests/test_opencode_installer.py:331-334` (`test_build_opencode_config_top_level_keys`); also covered end-to-end by snapshot test |
| 3 | Permission block contents (`spec.md:41-49`, no Scenario) | [PASS] COMPLIANT | `src/ai_harness/artifacts/installers/opencode.py:43-71` (`_PERMISSION_BLOCK` literal matches the spec table verbatim — 15 external_directory rules, 2 read/edit rules, 6 bash rules) |
| 4 | Exactly 16 agents (`spec.md:60-64`) | [PASS] COMPLIANT | `tests/test_opencode_installer.py:164-190` (`test_agent_definitions_has_exactly_16_entries` + `..._ids_match_target_set`); `:349-352` (`test_build_opencode_config_has_exactly_16_agents`); `tests/test_install.py:77-96` (integration check) |
| 5 | File-ref prompts use `{{HOME}}`-substituted paths (`spec.md:75-78`) | [PASS] COMPLIANT | `src/ai_harness/artifacts/installers/opencode.py:200` (`f"{{file:{{{{HOME}}}}/.config/opencode/prompts/{ns}/{agent.agent_id}.md}}"`); generic installer substitutes `{{HOME}}` at write time per `installer.py:_prepare_content`; integration test `test_install_copies_opencode_configuration` reads back the installed file and the `{{HOME}}` is resolved |
| 6 | Inlined prompts reflect on-disk `.md` at install time (`spec.md:80-83`) | [PASS] COMPLIANT | `tests/test_install.py:254-278` (`test_inline_prompt_reflects_md_edit` — mutation test, try/finally restores file, asserts `MUTATION_MARKER` prefix on `data["agent"]["review-risk"]["prompt"]`); `tests/test_opencode_installer.py:432-450` (byte-for-byte `rstrip("\n")` match against on-disk body) |
| 7 | Sub-phase models pinned (`spec.md:99-103`) | [PASS] COMPLIANT | `tests/test_opencode_installer.py:369-386` (`test_build_opencode_config_subphase_models_match_map` — asserts all 8 model values); `:389-401` (`test_build_opencode_config_jd_review_have_no_model` — asserts no `model` key on the 7 jd-*/review-* agents); `:363-366` (orchestrator model `openai/gpt-5.5`) |
| 8 | 6 read-only agents deny edit; `jd-fix-agent` does not (`spec.md:113-117`) | [PASS] COMPLIANT | `tests/test_install.py:311-339` (`test_readonly_agents_deny_edit` — asserts `permission == {"edit": "deny"}` on 6 agents and `"permission" not in data["agent"]["jd-fix-agent"]`); `tests/test_opencode_installer.py:469-486` (unit-level mirror) |
| 9 | Orchestrator allowlist is exactly 15 entries (16 keys incl. `*`); no `sdd-init`/`sdd-onboard` (`spec.md:125-129`) | [PASS] COMPLIANT | `tests/test_install.py:284-305` (`test_orchestrator_allowlist_has_15_entries`); `tests/test_opencode_installer.py:103-132` (5 unit tests covering total count, wildcard, both orphans absent, all 15 sub-agents present) |
| 10 | Deep-equal against target reference (`spec.md:142-146`) | [PASS] COMPLIANT | `tests/test_install.py:194-230` (`test_opencode_json_matches_target_reference` — full install pipeline → loads generated `opencode.json` → loads reference → substitutes `/home/diegoagd10` → `json.dumps(..., indent=2, sort_keys=True)` deep-equal). Re-ran in isolation: **PASSED in 0.10s** |

**Compliance summary**: 10/10 scenarios compliant. No `UNTESTED` or
`FAILING` items.

---

## 2. ADR Compliance

The proposal defines ADR-01 through ADR-06; design.md adds ADR-07 and
ADR-08. All 8 honored.

| ADR | Decision | Status | Evidence (file:line) |
|-----|----------|--------|----------------------|
| **ADR-01** | Prompt source = on-disk `.md` files, read at install time | [PASS] Honored | `src/ai_harness/artifacts/installers/opencode.py:147-161` (`_load_inlined_prompt` — the ONLY I/O site, body read via `read_text(encoding="utf-8")` then `rstrip("\n")` to match the reference's no-trailing-newline convention); mutation test `tests/test_install.py:254-278` proves read-at-install-time |
| **ADR-02** | `AGENT_DEFINITIONS: list[AgentDefinition]` in `opencode.py`; no external data file | [PASS] Honored | `src/ai_harness/artifacts/installers/opencode.py:212-391` (16 entries, role-grouped: 1 orchestrator + 7 sdd sub-phases + 3 jd + 4 review) |
| **ADR-03** | Drop orphan `sdd-init`/`sdd-onboard` allowlist entries | [PASS] Honored | `src/ai_harness/artifacts/installers/opencode.py:164-176` (`_build_orchestrator_allowlist` iterates `AGENT_DEFINITIONS`, skips `sdd-orchestrator`, emits all 15 sub-agents; orphans never appear); `openspec/CHANGELOG.md:10-18` documents the breaking change; `pyproject.toml:3` bumped to `0.2.0` |
| **ADR-04** | Permission block = hardcoded dict literal in `opencode.py` | [PASS] Honored | `src/ai_harness/artifacts/installers/opencode.py:43-71` (`_PERMISSION_BLOCK`); `:73-89` (`_DENY_PATHS`); single consumer (this installer) — extraction would be premature |
| **ADR-05** | `jd-fix-agent` keeps edit tools AND no `permission.edit.deny` | [PASS] Honored | `src/ai_harness/artifacts/installers/opencode.py:306-317` (`jd-fix-agent` row: `permission=None`; tools include `edit: True`; inline comment at `:312-313` cites ADR-05); `tests/test_install.py:337-339` asserts `"permission" not in data["agent"]["jd-fix-agent"]` |
| **ADR-06** | Snapshot test = deep-equal against target reference with `{{HOME}}` placeholder | [PASS] Honored | `tests/test_install.py:194-230` (loads `reference/target-opencode.json` from change folder, substitutes `/home/diegoagd10` → `tmp_path`, deep-equal via `json.dumps(..., indent=2, sort_keys=True)`) |
| **ADR-07** (design) | Drop `prompt_ns`; derive from prefix via `_prompt_ns` | [PASS] Honored | `src/ai_harness/artifacts/installers/opencode.py:131-144` (3-branch dispatch: `sdd-` → `sdd`, `jd-` → `jd`, `review-` → `review`; `ValueError` on unknown); AgentDefinition has 8 fields, not 10 |
| **ADR-08** (design) | Drop `prompt_body_override`; read from disk at install time | [PASS] Honored | AgentDefinition has no `prompt_body_override` field; bodies are read at install time via `_load_inlined_prompt` at `:160` |

---

## 3. Test / Lint / E2E Results (re-run)

### 3.1 pytest (full suite)

Re-ran `uv run pytest` (no flags). **273/273 passed**, 0 failed, 0
skipped. Match the apply report exactly (273 = 232 baseline + 41 new).

```
collected 273 items
tests/test_catalog.py ....                                               [  1%]
tests/test_claude_installer.py .......                                   [  4%]
tests/test_cli_sdd.py ..............                                     [  9%]
tests/test_copilot_installer.py ........                                 [ 12%]
tests/test_frontmatter.py ...                                            [ 13%]
tests/test_install.py .....................                              [ 20%]
tests/test_installer.py ...............                                  [ 26%]
tests/test_instructions.py ......                                        [ 28%]
tests/test_json_compat.py ..........                                     [ 32%]
tests/test_manifest.py ...                                               [ 33%]
tests/test_opencode_installer.py .....................................   [ 46%]
tests/test_permissions.py .......................                        [ 55%]
tests/test_prompt_inventory.py ....                                      [ 56%]
tests/test_rendering.py ............                                     [ 61%]
tests/test_resolver.py ...................................               [ 73%]
tests/test_state.py .........                                            [ 77%]
tests/test_uninstall.py ....................                             [ 84%]
tests/test_verifyreport.py .......................                       [ 93%]
tests/test_wizard.py ................                                    [ 98%]
tests/test_wizard_rendering.py ...                                       [100%]

============================= 273 passed in 1.56s ==============================
```

Snapshot test in isolation (`tests/test_install.py::test_opencode_json_matches_target_reference`):
```
collected 1 item
tests/test_install.py::test_opencode_json_matches_target_reference PASSED [100%]
============================== 1 passed in 0.10s ===============================
```

### 3.2 ruff format

Re-ran `uv run ruff format --check .`:
```
64 files already formatted
```
No drift. [PASS]

### 3.3 ruff check

Re-ran `uv run ruff check .`:
```
All checks passed!
```
No lint errors or warnings. [PASS]

### 3.4 e2e docker

Re-ran `e2e/docker-test.sh` (Docker 29.5.3 available in this env):
```
=== Tool Lifecycle: all assertions passed
=== Harness Lifecycle: fresh install
  PASS: fresh install assertions
=== Harness Lifecycle: reinstall with pre-existing state
  PASS: user-authored skill preserved
  PASS: user-authored custom prompt preserved
  PASS: reinstall with preservation assertions
=== Harness Lifecycle: uninstall
  PASS: pre-existing opencode AGENTS.md restored
  PASS: pre-existing opencode.json restored
  PASS: pre-existing prompts/sdd/sdd-apply.md restored
  PASS: user-authored skill preserved after uninstall
  PASS: user-authored prompt preserved after uninstall
  PASS: claude permissions rules removed on uninstall
  PASS: claude permissions marker deleted on uninstall
  PASS: claude settings backup preserved after uninstall
=== Harness Lifecycle: all uninstall assertions passed
=== Copilot CLI Lifecycle: fresh install
  PASS: copilot-instructions.md present (fresh)
  PASS: all 16 copilot agents present (fresh)
  PASS: hook JSON validated (fresh)
  PASS: fresh install assertions
=== Copilot CLI Lifecycle: reinstall with pre-existing state
  PASS: user-authored agent preserved
  PASS: stale copilot agent overridden (backup created)
  PASS: copilot instructions backed up on reinstall
  PASS: reinstall with preservation assertions
=== Copilot CLI Lifecycle: idempotent override
  PASS: all 16 copilot agents present (idempotent)
  PASS: hook JSON validated (idempotent)
  PASS: idempotent override assertions
=== Copilot CLI Lifecycle: uninstall
  PASS: pre-existing copilot instructions restored
  PASS: user-authored agent preserved after uninstall
=== Copilot CLI Lifecycle: all uninstall assertions passed
=== Wizard Lifecycle: install --all state file
  PASS: state file written with all three agents after install --all
=== Wizard Lifecycle: uninstall --all state file
  PASS: state file deleted after uninstall --all
=== Wizard Lifecycle: all state file assertions passed
=== SDD Lifecycle: sdd-status — explicit change name
  PASS: explicit change — changeName=my-change, nextRecommended=verify
=== SDD Lifecycle: sdd-status — inferred change
  PASS: inferred change — changeName=inferred
=== SDD Lifecycle: sdd-status — --instructions
  PASS: --instructions includes phaseInstructions for verify
=== SDD Lifecycle: sdd-status — missing change
  PASS: missing change → sdd-new with blockedReasons
=== SDD Lifecycle: sdd-status — no active changes
  PASS: no active changes → sdd-new
=== SDD Lifecycle: sdd-status — pending tasks (not ready)
  PASS: pending tasks — total=1, completed=0, nextRecommended=apply
=== SDD Lifecycle: all sdd-status assertions passed
=== SDD Lifecycle: sdd-continue — dispatcher markdown
  PASS: dispatcher markdown contains header, deps, next, JSON block
=== SDD Lifecycle: sdd-continue — --json mode
  PASS: --json mode — changeName=continue-change, nextRecommended=verify, phaseInstructions=present
=== SDD Lifecycle: sdd-continue — pending tasks (not ready)
  PASS: dispatcher markdown for pending change — output length=3340
=== SDD Lifecycle: all sdd-continue assertions passed
=== SDD Lifecycle: workspace_root cleanup
  PASS: workspace_root() → /tmp/e2e-sdd-ws-a02j1nn5 (writable, then removed by cleanup)

=== All e2e categories passed ===
```

All e2e categories pass. [PASS]

---

## 4. Snapshot Test / Deep-Equal Result

Re-ran the snapshot test in isolation: **PASSED**.

Re-implemented the deep-equal at the Python level (so the verifier can
inspect structurally) using normalized placeholders on both sides
(replacing `/home/diegoagd10` in the reference AND `{file:{{HOME}}/...}`
in the generated config with a common `{file:{{HOME}}/...}` token):

```
DEEP_EQUAL (after {{HOME}} normalization): True
```

The in-memory `_build_opencode_config(prompts_root)` output and the
locked target reference at
`openspec/changes/install-opencode-template/reference/target-opencode.json`
are structurally identical after normalizing the runtime-home path on
both sides.

**Deltas**: none beyond the documented deviations (see §5).

---

## 5. Deviation Review (apply report §"Deviations from Design")

The apply report listed 4 deviations. Each was independently verified.

### Deviation 1: Target reference bug — drop orphan `sdd-init`/`sdd-onboard`

The reference at `openspec/changes/install-opencode-template/reference/target-opencode.json`
was read end-to-end. Confirmed: the `sdd-orchestrator.permission.task`
block (lines 44-60) contains **15 sub-agents + `*` = 16 keys**;
`sdd-init` and `sdd-onboard` are NOT present.

Spec coverage: `spec.md:121-129` ("MUST NOT include `sdd-init` or
`sdd-onboard`") + scenario at `spec.md:125-129` ("Allowlist is exactly
15 entries"). The spec, design, and ADR-03 are unanimous. The orphan
drop is correct.

[CONFIRMED — deviation is valid]

### Deviation 2: Target reference bug — Unicode vs straight quotes

Re-read the four review-agent prompt bodies in the reference
(lines 117, 130, 143, 156). The text uses `\u2014` (em-dash) which is
preserved on both sides (`description` field and the prompt body's own
em-dashes). No `\u2018`/`\u2019` (curly single quotes) found in the
inlined bodies — confirmed all single quotes are straight `'`.

[CONFIRMED — deviation is valid; reference matches the on-disk `.md`
files for the four review prompts]

### Deviation 3: Trailing newline in inlined prompts

`_load_inlined_prompt` at `src/ai_harness/artifacts/installers/opencode.py:161`
does `body.rstrip("\n")`. The `rstrip("\n")` strips ONLY a single
trailing newline (or none, or multiple — `rstrip` is greedy on a single
character class). The snapshot test passes — confirmed.

Note: `rstrip("\n")` is technically greedy: it strips ALL trailing `\n`
characters, not just one. The apply report and docstring say "single
trailing newline". This is a **minor docstring imprecision** — the
behavior is fine (no on-disk `.md` file ends in multiple `\n` so the
behavior is identical) but the comment is mildly misleading. Flagged
as a NIT, not a blocker.

[CONFIRMED — snapshot test passes; behavior is correct]

### Deviation 4: `_build_opencode_config` signature change

The signature is now `_build_opencode_config(prompts_root: Path) -> dict[str, object]`
at `src/ai_harness/artifacts/installers/opencode.py:400`.

**Caller audit** (searched the repo for `_build_opencode_config`):
- `src/ai_harness/artifacts/installers/opencode.py:492` — production
  caller in `_build_manifest`: passes `self._catalog.get_root() / "prompts"`.
- `e2e/test_harness_lifecycle.py:73` — e2e helper, updated to
  `_build_opencode_config(RESOURCES_DIR / "prompts")`. Confirmed via
  `git diff e2e/test_harness_lifecycle.py` (the diff is exactly the
  signature update + a 2-line docstring extension about why the helper
  is pointed at the real prompts dir).
- All other matches are imports or docstring references — no other
  call sites.

[CONFIRMED — single production caller + single e2e caller, both updated]

---

## 6. CHANGELOG & Version Bump

| Check | Status | Evidence |
|-------|--------|----------|
| `openspec/CHANGELOG.md` exists and cites `sdd-init`/`sdd-onboard` drop | [PASS] | `openspec/CHANGELOG.md:1-40` — new file, `## 0.2.0 — 2026-06-17 — install-opencode-template` entry with full "Breaking change" callout on lines 10-18 |
| `pyproject.toml` version bumped from 0.1.0 → 0.2.0 | [PASS] | `pyproject.toml:3` — `version = "0.2.0"` (was 0.1.0 per apply report) |

---

## 7. Deep-Modules Review of `opencode.py`

**Overall**: deep, well-bounded module. The 4 helpers each have a
single, clear purpose; `_build_opencode_config` is a thin orchestrator
well under the 25-line ceiling.

### `_build_opencode_config` orchestrator

Body (lines 414-427) is **14 lines** including the return statement —
well under the 25-line cap. One concern per branch, no embedded data.
Delegates to `_load_inlined_prompt`, `_build_agent_entry`, and
`_build_orchestrator_allowlist`. [PASS — thin orchestrator]

### Helper-by-helper assessment

| Helper | Purpose | Concern count | LOC | Status |
|--------|---------|---------------|-----|--------|
| `_prompt_ns(agent_id)` (`:131-144`) | prefix → namespace dispatch | 1 (the dispatch itself) | 14 | [PASS] Single purpose. Note: name could be slightly more specific (`_namespace_for_agent_id`) but the underscore + locality make it readable in context. |
| `_load_inlined_prompt(prompts_root, agent_id)` (`:147-161`) | read .md body verbatim, normalize trailing newline | 1 (read + rstrip) | 15 | [PASS] Single I/O site (ADR-01). |
| `_build_orchestrator_allowlist()` (`:164-176`) | build `{"*":"deny", <15 sub-agents>:"allow"}` | 1 (the allowlist composition) | 13 | [PASS] Single purpose. |
| `_build_agent_entry(agent, prompt_body)` (`:179-205`) | compose one agent's JSON dict from its `AgentDefinition` | 1 (per-field emission) | 27 | [PASS] Each branch emits one field; no embedded data. |

### `AgentDefinition` — 8-field review

| Field | Status | Notes |
|-------|--------|-------|
| `agent_id` | [PASS] Required (the dict key). |
| `description` | [PASS] Spec-mandated field on every agent. |
| `mode: Literal["primary","subagent"]` | [PASS] Spec-mandated. Drives the orchestrator/sdd split. |
| `hidden: bool` | [SUGGESTION] Foldable: every entry has `hidden == (mode == "subagent")` — `sdd-orchestrator` is `mode="primary"` + `hidden=False`; all 15 sub-agents are `mode="subagent"` + `hidden=True`. Could be derived inside `_build_agent_entry` as `if agent.mode == "subagent": entry["hidden"] = True` and the field dropped from the dataclass. Per Ousterhout "fold what can be derived", this is a code smell — but not a blocker (no behavioral impact, the snapshot test still passes). |
| `model: str \| None` | [PASS] Optional per-agent model. |
| `permission: dict \| None` | [PASS] Optional per-agent permission block. |
| `tools: dict[str, bool]` | [PASS] Spec-mandated; distinct from the agent-level `mode`/description. |
| `prompt_kind: Literal["file_ref","inline"]` | [PASS] Drives the dispatch in `_build_agent_entry`. |

**Verdict on `AgentDefinition`**: 7 of 8 fields are necessary and
orthogonal. `hidden` is a candidate for folding (see SUGGESTION §8.1).

---

## 8. Issues Found

**CRITICAL**: None.

**WARNING**: None.

**SUGGESTION**:

1. **Foldable `hidden` field on `AgentDefinition`** —
   `src/ai_harness/artifacts/installers/opencode.py:121`. Across all
   16 entries, `hidden == (mode == "subagent")`. Per Ousterhout "fold
   what can be derived" (`coding-guidelines` deep-modules.md), this is
   a candidate for removal. **Fix direction**: drop the field from
   the dataclass and emit `entry["hidden"] = True` inside
   `_build_agent_entry` when `agent.mode == "subagent"`. Add a
   unit-level invariant test asserting the fold. The snapshot test
   would continue to pass (emission is preserved).

2. **Docstring imprecision at `:155-157`** — the docstring says
   "Strips a single trailing newline" but `rstrip("\n")` is greedy on
   the `\n` character class and will strip multiple trailing newlines.
   On-disk `.md` files all end in exactly one `\n` so behavior is
   correct, but the comment is mildly misleading. **Fix direction**:
   rewrite as "Strips trailing newlines so the inlined string matches
   the target reference's no-trailing-newline convention." (No code
   change needed.)

3. **NIT — `rstrip` choice**: `rstrip("\n")` strips any number of
   trailing `\n` characters. `rstrip("\n", 1)` is not valid Python
   syntax; the closest equivalent is `body[:-1] if body.endswith("\n")
   else body` or `body.removesuffix("\n")` (3.9+). On-disk files end
   in one `\n` so the behavior is identical; no test changes needed.
   Mentioned only because it's adjacent to suggestion #2.

---

## 9. Final Verdict

**PASS** — 10/10 spec scenarios compliant, 8/8 ADRs honored, 273/273
tests pass, lint and format clean, e2e green, CHANGELOG and version
bump in place, deep-equal against the target reference holds after
runtime-home normalization, no regressions, no critical or warning
findings. The 3 SUGGESTIONs above are minor (one foldable field, two
docstring nits) and do not block archive.

**Next recommended phase**: `sdd-archive`.
