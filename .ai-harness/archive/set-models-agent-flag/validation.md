---
change: set-models-agent-flag
artifact: validation
verdict: pass-with-warnings
critical: 0
---

# Validation — set-models-agent-flag

## Verdict
verdict: pass-with-warnings
critical: 0

All 12 RFC 2119 requirements are implemented; all 8 GIVEN/WHEN/THEN scenarios
have at least one enforcing test (direct or via code-path proof); the nine
edge cases from `exploration.md` are covered; forbidden files
(`renderers.py`, `operations.py`, `models.py`) are untouched; every
out-of-scope item from the PRD is respected (claude silent-only, re-render
unchanged, template-default limitation untouched, strict-lowercase enforced,
no per-agent cleanup); `mypy --strict` baseline is preserved exactly (31
errors before and after — zero NEW); `ruff check`/`ruff format --check`
clean; `pytest tests/test_set_models.py` 152 passed; `pytest tests/`
417 passed; e2e module imports cleanly. The only finding is one
WARNING-level commit-hygiene drift: two of the five commit subjects are
53 chars, 3 over the conventional 50-char soft limit. No AI attribution,
no `Co-Authored-By` lines. Recommendation: pass-with-warnings — slice is
ready to archive.

## Critical findings
None.

## Warnings
1. **Commit subjects exceed the 50-char soft limit on 2 of 5 commits.**
   `feat(set-models): add -a/--agent flag with validation` (53 chars,
   commit `4e30c03`) and `feat(wizard): honor -a agent mode for opencode
   wizard` (53 chars, commit `86637ff`). Conventional Commits recommends
   ≤50 char subjects; the audit checklist classifies commit-hygiene drift
   as WARNING. Body content is clean and informative in both cases, so
   the message itself is healthy — only the subject length is over budget.

## Suggestions
1. **Help-text test uses a `contains` substring check, not a full regex.**
   `test_cli_set_models_help_mentions_agent_flag_and_valid_values`
   asserts each token (`-a`, `--agent`, `loop`, `change`, `claude`,
   `ignored`/`ignore`) appears in the lowered output. The PRD success
   criteria pin the wording, including the phrase
   `"Ignored for claude."`. A regex over the rendered help (e.g.
   `r"loop.+change.+Ignored for claude"`) would also catch accidental
   reorderings. Not blocking — current test pins the must-have tokens.
2. **`test_cli_set_models_agent_flag_with_claude_is_silently_ignored`
   patches `run_wizard_or_bail` directly rather than driving it through
   `CliRunner` + a real stdin TTY.** The patching is necessary because
   `CliRunner` has no TTY and the wizard needs one. The choice is
   defensible (the test name says "silently ignored" and the assertions
   on byte output + override store are sound), but a follow-up comment
   could explicitly point readers at why the patch is the right shape
   (today's `run_wizard_or_bail` TTY guard short-circuits before the
   body runs under `CliRunner`). Pure doc polish.

## Spec coverage table

| Requirement ID | Commit | File:Line | Result |
| --- | --- | --- | --- |
| `req:vocab-opencode-change-agents-001` | `3eb062b` | `src/ai_harness/modules/wizard/pure.py:151-160` | PASS — tuple of 8 names in spec order, typed `tuple[str, ...]` |
| `req:vocab-opencode-change-agents-002` | `3eb062b` | `src/ai_harness/modules/wizard/pure.py:163-165` | PASS — accessor `opencode_change_agents()` returns the same tuple object (identity-stable test pins `is`) |
| `req:cli-flag-agent-001` | `4e30c03` | `src/ai_harness/commands/set_models.py:33-44, 95-98` | PASS — typer `Option("-a","--agent")`, raw `str`, default `"loop"`, routed via `parse_agent_mode` |
| `req:cli-flag-agent-002` | `4e30c03` | `src/ai_harness/commands/set_models.py:97-98` | PASS — `typer.BadParameter(str(exc))` names `loop, change`; exit code 2 verified live |
| `req:cli-flag-agent-003` | `4e30c03` | `src/ai_harness/commands/set_models.py:44` | PASS — default literal `"loop"`; byte-equality proven by `test_cli_set_models_default_agent_flag_is_loop` |
| `req:wizard-opencode-agent-set-001` | `4e30c03` | `src/ai_harness/modules/wizard/tui.py:1046` | PASS — `run_wizard_or_bail(cli, *, home, agent_mode=AgentMode.LOOP)`; `AgentMode` exported from `pure.py` |
| `req:wizard-opencode-agent-set-002` | `86637ff` | `src/ai_harness/modules/wizard/tui.py:1033-1035` | PASS — `run_wizard` dispatcher selects `opencode_change_agents()` vs `opencode_wizard_agents()` once, passes as `agents` kwarg |
| `req:wizard-opencode-agent-set-003` | `86637ff` | `src/ai_harness/modules/wizard/tui.py:848-852` (signature) + body grep | PASS — `run_opencode_wizard` body contains no calls to `opencode_wizard_agents()` or `opencode_change_agents()` (grep confirms only line 1034 in dispatcher) |
| `req:wizard-claude-agent-flag-ignored-001` | `ba9d798` | `src/ai_harness/modules/wizard/tui.py:619-635` | PASS — `run_claude_wizard` body has zero `agent_mode` references (grep); docstring states parameter is accepted for symmetry and ignored |
| `req:wizard-claude-agent-flag-ignored-002` | `ba9d798` | `src/ai_harness/modules/wizard/tui.py:640-687` | PASS — Claude body uses `claude_wizard_agents()` only; override store can't gain change-agent keys; test pins no `change-`/`propose`/`design`/`specs`/`tasks` keys |
| `req:help-text-honest-001` | `4e30c03` | `src/ai_harness/commands/set_models.py:35-43` (help text) | PASS — `--help` output contains `-a`, `--agent`, `loop`, `change`, `claude`, `ignored` (test pins) |
| `req:re-render-scope-001` | `86637ff` | `src/ai_harness/modules/wizard/tui.py:1002-1003` | PASS — `re_render_for_agent_clis([AgentCli.OPENCODE], home=home)` unchanged; `_discover_loop_agents()` untouched; test asserts all 12 files exist on disk after `-a change` confirm |

## Scenario coverage table

| Scenario | Test file:line | Enforcement |
| --- | --- | --- |
| 1 — `-a change` targets 8 change agents | `tests/test_set_models.py:1216-1280` + `:1283-1345` | Direct — 8 override keys, 12 re-rendered files, model in frontmatter |
| 2 — `-a loop` preserves today's behavior byte-for-byte | Indirect — `tests/test_set_models.py:2163-2196` (default-is-loop) + pre-existing loop-branch tests now passing `agents=` | Code-path — same body with same data flow |
| 3 — Claude with `-a change` runs silently | `tests/test_set_models.py:1353-1428` | Direct — override store has no change-agent keys, no `ignored`/`warning`/`note` in output |
| 4 — Claude with no `-a` runs Claude wizard (today) | Same as scenario 3 (byte-equality under unchanged claude body) | Code-path — body identical regardless of `agent_mode` |
| 5 — `-a` omitted defaults to `loop` | `tests/test_set_models.py:2163-2196` | Direct — patched `run_wizard_or_bail` captures `AgentMode.LOOP` |
| 6 — `-a bogus` rejected with valid-set hint | `tests/test_set_models.py:2202-2216` + `e2e/set_models_lifecycle.py:148-177` | Direct at both layers — non-zero exit, both `loop` and `change` in combined output |
| 7 — `-a LOOP` (uppercase) rejected | `tests/test_set_models.py:2218-2230` + `:184-196` (parser-level) | Direct — `test_parse_agent_mode_rejects_uppercase_strict_lowercase` covers `LOOP`, `Loop`, `CHANGE`, `cHaNgE`; CLI test pins `LOOP` exit code + valid-values hint |
| 8 — Ctrl+C writes nothing | `tests/test_set_models.py:957-` (existing `test_run_opencode_wizard_ctrl_c_at_model_phase_writes_nothing`, modified to pass `agents=`) | Code-path — body unchanged beyond `agents=` kwarg; cancel branch verified |

## Edge-case walk

| Edge case | Status | Evidence |
| --- | --- | --- |
| `-a change` + `-o claude` silently ignored | ✅ verified by test | `test_cli_set_models_agent_flag_with_claude_is_silently_ignored` |
| `-a change` + `-o opencode` targets 8 agents | ✅ verified by test | `test_run_opencode_wizard_change_agent_set_writes_eight_overrides` |
| `-a` omitted → defaults to `loop` | ✅ verified by test | `test_cli_set_models_default_agent_flag_is_loop` |
| `-a bogus` rejected with valid-set hint, exit 2 | ✅ verified by test + e2e | `test_cli_set_models_unknown_agent_flag_errors` + e2e `_test_set_models_unknown_agent_flag_errors`; live CLI confirmed exit 2 |
| `-a LOOP` (uppercase) — strict-lowercase enforced | ✅ verified by test | `test_cli_set_models_uppercase_agent_flag_errors` + `test_parse_agent_mode_rejects_uppercase_strict_lowercase` (covers `LOOP`, `Loop`, `CHANGE`, `cHaNgE`) |
| Ctrl+C writes nothing (any `-a`) | ⚠️ verified by code path | `test_run_opencode_wizard_ctrl_c_at_model_phase_writes_nothing` already exercised the opencode wizard body; only kwarg `agents=` was threaded (slice-3); body unchanged → cancel contract preserved |
| `-a change` followed by `-a loop` — store side-by-side, no collisions | ✅ verified by data shape | 8 change-agent keys (`change-orchestrator`, `change-explorer`, `change-implementor`, `change-validator`, `propose`, `design`, `specs`, `tasks`) are distinct from 4 loop-agent keys; deep-merge of `write_override_store` handles side-by-side |
| OpenCode binary absent — `_a` irrelevant on this path | ⚠️ verified by code path | `run_wizard_or_bail` checks `_resolve_opencode_binary()` (line 1070-1078) before consuming `agent_mode`; binary guard fires first |

## Forbidden-file check

| File | Touched in any of the 5 commits? |
| --- | --- |
| `src/ai_harness/modules/harness/renderers.py` | NO |
| `src/ai_harness/modules/harness/operations.py` | NO |
| `src/ai_harness/modules/harness/models.py` | NO |

Files actually touched by the 5 commits (`git diff 38e42f6..HEAD --stat`):

| Commit | Files |
| --- | --- |
| `3eb062b` (Slice 1) | `src/ai_harness/modules/wizard/pure.py`, `tests/test_set_models.py` |
| `4e30c03` (Slice 2) | `src/ai_harness/commands/set_models.py`, `src/ai_harness/modules/wizard/tui.py`, `tests/test_set_models.py` |
| `86637ff` (Slice 3) | `src/ai_harness/modules/wizard/tui.py`, `tests/test_set_models.py` |
| `ba9d798` (Slice 4) | `src/ai_harness/modules/wizard/tui.py`, `tests/test_set_models.py` |
| `cfeffd1` (Slice 5) | `e2e/set_models_lifecycle.py` |

Seam intact.

## Gate results

| Command | Result |
| --- | --- |
| `ruff check src tests e2e` | PASS — "No issues found" |
| `ruff format --check src tests e2e` | PASS — "35 files already formatted" |
| `mypy --strict src/ai_harness/commands/set_models.py src/ai_harness/modules/wizard/pure.py src/ai_harness/modules/wizard/tui.py` (post-change) | 31 errors (matches baseline) |
| `mypy --strict` same files at parent commit `38e42f6` (pre-change baseline) | 31 errors — same set |
| Net new mypy errors introduced by the 5 commits | **0** |
| `pytest tests/test_set_models.py -x -q` | 152 passed |
| `pytest tests/ -x -q` | 417 passed |
| `e2e/set_models_lifecycle.py` import check | imports cleanly under `uv run --with typer --with questionary` |
| Live `ai-harness set-models -o opencode -a bogus` exit code | 2 (typer `BadParameter` mapping confirmed) |

Baseline mypy verification: ran `mypy --strict` against the three touched files
with `git checkout 38e42f6 --` applied, then restored the working tree. Pre and
post counts match exactly — zero regressions introduced.

## Commit hygiene

| Check | Result |
| --- | --- |
| Conventional Commits format | PASS — 5/5 use `feat(...)` / `test(...)` types |
| Subject ≤ 50 chars | FAIL soft — 2/5 subjects are 53 chars (`4e30c03`, `86637ff`); see WARNING #1 |
| Body present when useful | PASS — 5/5 have informative bodies explaining slice scope and linking requirement IDs |
| `Co-Authored-By` line | PASS — none in any commit |
| AI attribution (`Generated with`, `Claude`, `Anthropic`, etc.) | PASS — none |
| One task = one commit | PASS — 5 commits, 5 slices (1 vocab, 2 CLI flag, 3 opencode wiring, 4 claude ignore, 5 e2e) |