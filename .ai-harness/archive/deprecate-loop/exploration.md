# Exploration — deprecate-loop

## Budget
1000

## Affected Files

### A. Resources — delete entirely
- `src/ai_harness/resources/loop-agent/explorer.md` — loop subagent prompt (66 lines)
- `src/ai_harness/resources/loop-agent/implementor.md` — loop subagent prompt (67 lines)
- `src/ai_harness/resources/loop-agent/loop-orchestrator.md` — loop primary agent prompt (228 lines)
- `src/ai_harness/resources/loop-agent/_result-contract.md` — shared contract referenced by loop prompts (55 lines)
- `src/ai_harness/resources/loop-agent/validator.md` — loop subagent prompt (127 lines)
- Total resource deletions: 543 lines

### B. Source — wizard pure layer
- `src/ai_harness/modules/wizard/pure.py` — Remove `AgentMode.LOOP`; collapse `AgentMode` to single-member `CHANGE`; update `parse_agent_mode` (error message no longer names "loop"); remove `OPENCODE_WIZARD_AGENTS` constant and `opencode_wizard_agents()` function; update `CLAUDE_WIZARD_AGENTS` from the three loop subagents (`explorer`, `implementor`, `validator`) to the eight change subagents (`change-explorer` through `change-tasks`, excluding `change-orchestrator` which is a skill in Claude)

### C. Source — wizard TUI layer
- `src/ai_harness/modules/wizard/tui.py` — Remove `opencode_wizard_agents` from imports; remove loop branch in `run_wizard` (always use `opencode_change_agents()`); change `agent_mode` default from `AgentMode.LOOP` to `AgentMode.CHANGE` in `run_claude_wizard`, `run_wizard`, and `run_wizard_or_bail`; update comment claiming the Claude wizard ignores `agent_mode` (now irrelevant, but the signature symmetry argument still holds); update re-render docstrings that say "loop agents"; the `run_claude_wizard` body references `claude_wizard_agents()` which changes automatically once `pure.py` is updated

### D. Source — renderers
- `src/ai_harness/modules/harness/renderers.py` — Remove `"loop-agent"` from `_AGENT_RESOURCE_DIRS` tuple (becomes `("change-agent",)` only); remove four loop entries from `_AGENT_META` dict (`"loop-orchestrator"`, `"explorer"`, `"implementor"`, `"validator"`); rename private `_discover_loop_agents` to `_discover_agents` (internal only, callers in this file and in tests); update all docstrings/comments that say "loop agents" or "loop agent templates"

### E. Source — set-models command
- `src/ai_harness/commands/set_models.py` — Change `-a/--agent` default from `"loop"` to `"change"`; update help text to remove the "loop for the four loop agents" phrasing; update inline comment referencing "loop" or "change" selection

### F. Source — operations
- `src/ai_harness/modules/harness/operations.py` — Update docstrings that say "rendered loop agents" → "rendered change agents" in `re_render_for_agent_clis` and `_write_rendered_agents`

### G. Source — worktree
- `src/ai_harness/modules/harness/worktree.py` — Update module docstring (first line: "Git worktree isolation command for the loop workflow")

### H. Tests — renderers
- `tests/test_renderers.py` — Update `_discover_loop_agents` import to `_discover_agents`; update expected Claude path list (remove `loop-orchestrator` skill path, and remove `explorer`, `implementor`, `validator` subagent paths); update expected OpenCode path list (remove 4 loop agent paths); remove all tests whose subject is a loop agent: `test_loop_orchestrator_description_mentions_loop_labeled_sub_issues`, `test_claude_orchestrator_skill_frontmatter`, `test_claude_orchestrator_body_has_spawn_allowlist`, `test_claude_orchestrator_body_has_session_end_pr_contract`, `test_claude_orchestrator_body_has_prd_linking_keywords`, `test_claude_orchestrator_body_has_label_independent_drain_check`, `test_claude_orchestrator_is_skill_not_subagent`, `test_claude_subagents_have_no_color` (loop subset), the loop-orchestrator frontmatter/permission/color tests around lines 1357-1377, the loop-orchestrator override test around lines 1771-1790, the copilot loop agent path tests around lines 1995-2063; update `test_copilot_rendered_body_matches_template_verbatim` (removes `loop-agent` dir reference); update `_build_expected_opencode` / `_build_expected_claude` if they iterate `_NATIVE_AGENT_NAMES` (they iterate it from test_install.py)

### I. Tests — install
- `tests/test_install.py` — Remove `_LOOP_AGENT_NAMES = ("explorer", "implementor", "validator", "loop-orchestrator")`; update `_NATIVE_AGENT_NAMES` to only the 9 change agents; update `_CLAUDE_SUBAGENT_NAMES` to only 8 change subagents (removing `explorer`, `implementor`, `validator`); change `_CLAUDE_SKILL_NAME = "loop-orchestrator"` to `"change-orchestrator"` (now only one skill per install); update file-count assertions: Claude 19 → 15 (6+8+1), `"25 file(s)"` CLI assertion for both claude and copilot → `"21 file(s)"`, OpenCode 13 → 9, `"19 file(s)"` CLI assertion → `"15 file(s)"`; update override tests that reference `implementor.md` by path (lines 1130-1153) to use a change agent like `change-implementor`; rename `test_install_claude_writes_loop_agents` and similar test names; remove `test_install_copilot_rendered_body_matches_template_verbatim` loop-agent template reference

### J. Tests — set-models
- `tests/test_set_models.py` — Remove `opencode_wizard_agents` from import list; remove `test_opencode_wizard_agents_includes_orchestrator_first`; update `test_parse_agent_mode_accepts_loop_and_change` → only "change" is valid now; update `test_parse_agent_mode_rejects_unknown_value` → "loop" is now an invalid value and the error message no longer lists it; update `test_parse_agent_mode_rejects_uppercase_strict_lowercase` → remove "LOOP" / "Loop" cases; update every `run_opencode_wizard(home=..., agents=opencode_wizard_agents())` call → `opencode_change_agents()`; update `test_run_opencode_wizard_change_agent_set_re_renders_change_agent_files` docstring from "13" to "9" and assertion from 13 to 9 files; update `test_run_opencode_wizard_no_back_choice_in_first_model_phase_agent_chooser` which calls `tui._ask_opencode_continue_or_agent("model", {}, opencode_wizard_agents())`

### K. Docs
- `README.md` — Remove or rewrite the "Running the loop in a worktree" section; update "ai-harness install" description that names loop agents; update "Copilot loop agents" section; remove loop agents from the workflow diagram (`to-issues → loop`); update any file path references to `loop-agent/`
- `CONTEXT.md` — Remove the "Loop agents" vocabulary entry and the sentence describing `loop-orchestrator → explorer → implementor → validator`; remove the "loop session" description; update the "Vocabulary" section
- `CLAUDE.md` (project) — Update triage section: remove `` `loop` (= `LOOP_LABEL`) means queued for loop implementation ``; remove the note that sub-issues get `loop` label; update `/to-prd` / `/to-issues` publishing rules

### L. Potential check (may need minor update)
- `src/ai_harness/resources/skills/to-design/SKILL.md` — git grep hit; verify if it references the loop workflow or just uses "loop" as a generic term
- `docs/adr/0002-render-agents-per-cli.md` — git grep hit; likely just historical; add a deprecation note if it describes the loop agent set as current
- `docs/adr/0003-loop-pr-prd-linking.md` — loop ADR; add deprecation header or leave as historical record
- `docs/adr/0007-loop-worktree-isolation.md` — loop ADR; same treatment
- `docs/adr/0008-copilot-loop-agents-native-model.md` — loop ADR; same treatment

## Plan

1. **Delete `src/ai_harness/resources/loop-agent/`** — remove all 5 files. This immediately breaks the `_discover_loop_agents` discovery and the 4 `_AGENT_META` entries.

2. **Update `renderers.py`** — remove the loop entries from `_AGENT_RESOURCE_DIRS` and `_AGENT_META`; rename `_discover_loop_agents` to `_discover_agents` and update all internal call sites. Verify `render_agents` docstring no longer says "loop agents". This is the deepest module and drives most downstream change.

3. **Update `pure.py`** — collapse `AgentMode` to one member (`CHANGE` only); remove `OPENCODE_WIZARD_AGENTS` / `opencode_wizard_agents()`; update `CLAUDE_WIZARD_AGENTS` to the 8 change subagents; update `parse_agent_mode` error message.

4. **Update `tui.py`** — remove `opencode_wizard_agents` import; simplify `run_wizard` to always use `opencode_change_agents()`; update `agent_mode` defaults; update docstrings and inline comments referencing "loop agents".

5. **Update `set_models.py`** — change `-a` default to `"change"`, update help text.

6. **Update `operations.py` and `worktree.py`** — docstring-only changes.

7. **Update `tests/test_renderers.py`** — remove loop-agent test functions; update path lists and constants.

8. **Update `tests/test_install.py`** — replace `_LOOP_AGENT_NAMES`, update constants, file counts, and two override tests that reference `implementor`.

9. **Update `tests/test_set_models.py`** — remove `opencode_wizard_agents` references; update `AgentMode` tests; swap `opencode_wizard_agents()` for `opencode_change_agents()` in `run_opencode_wizard` call sites.

10. **Update `README.md`**, **`CONTEXT.md`**, **`CLAUDE.md`** — remove loop-workflow prose.

11. **Verify and update `to-design/SKILL.md`** and the loop ADR files if their "loop" mentions are about the loop agent set (not just the word "loop").

## Edge Cases

- `AgentMode` becomes a single-member `StrEnum`. A single-member StrEnum is valid Python, but `parse_agent_mode` must still raise on any input other than `"change"`. Callers that used to send `"loop"` get a `ValueError` and surface a `typer.BadParameter`; that is the desired behavior.
- `CLAUDE_WIZARD_AGENTS` changing from 3 to 8 agents expands the Claude wizard UI significantly. The wizard flow is the same but the user now sees 8 agents instead of 3. All downstream pure helpers (`build_model_picker_rows`, `build_effort_picker_rows`, `build_confirmation_rows`) work identically — they receive a tuple of strings and do not hard-code length.
- The `run_claude_wizard` body calls `claude_wizard_agents()` which automatically picks up the updated `CLAUDE_WIZARD_AGENTS` constant — no call site in `tui.py` needs separate patching for the wizard body.
- `_AGENT_META` entries for `explorer`, `implementor`, `validator` are removed. Any code that calls `get_agent_meta("explorer")` will raise `ValueError("Unknown agent template: 'explorer'")`. Tests currently doing this must be updated or removed.
- The re-render count: after removing loop agents, `_discover_agents()` finds 9 change agents. Tests asserting the old count of 13 files must be updated to 9. The tui.py comment claiming "12" (actually 13) is also stale and must be fixed.
- Install file counts change (see Affected Files section). Every hardcoded count assertion in unit tests and e2e must be updated.
- Override tests in `test_install.py` that use `implementor` as the test key (lines ~1130-1153) will fail because `implementor.md` no longer exists. Must change to a change agent like `change-implementor`.
- User machines with existing loop agent files on disk: `uninstall` reads the old manifest and removes the exact files it recorded. No explicit migration step is needed — existing loop agent files will be removed on the next `uninstall`. The new `install` will not write them, so they become orphaned until uninstalled.
- `CLAUDE.md` references the `loop` GitHub label for sub-issues. Removing the loop agent set does not automatically retire the GitHub label or change the `/to-issues` skill's labeling behavior. The triage docs update (CLAUDE.md, CONTEXT.md) decouples the label from the implementation.

## Test Surface

- `tests/test_renderers.py` — Render path lists for Claude and OpenCode updated; loop-orchestrator body tests removed; copilot agent list reduced from 13 to 9.
- `tests/test_install.py` — File count assertions updated (Claude: 19→15, OpenCode: 13→9, Copilot: 19→15, CLI outputs updated); loop subagent names removed from `_CLAUDE_SUBAGENT_NAMES`; override agent key changed from `implementor` to `change-implementor`.
- `tests/test_set_models.py` — `AgentMode` tests reduced to single valid value; `opencode_wizard_agents()` call sites replaced; wizard flow tests still valid (same mechanics, different agent set).
- `e2e/e2e_test.sh` (Tier 2) — `test_override_updates_installer_section` injects `{"implementor": ...}` override and then checks `implementor.md` file — this test will fail after loop agents are removed and must be updated to use a change agent name and path.
- All existing change-orchestrator body tests in `test_renderers.py` are unaffected (they test change-agent content, not loop-agent content).

## Risks

- **Test blast radius undercount**: `test_set_models.py` is 3693 lines and many wizard flow tests pass `agents=opencode_wizard_agents()`. Each is a 1-line swap but there are ~12-15 of them. If any are missed, the test passes but validates the wrong agent set. Mitigation: grep for `opencode_wizard_agents` before marking done.
- **`_discover_loop_agents` rename**: The function is imported by name in `tests/test_renderers.py` (line 22). If the rename is done in `renderers.py` but the test import is not updated, the test module fails to import. Mitigation: grep for `_discover_loop_agents` across the entire test surface.
- **`AgentMode` single-member enum**: `AgentMode.CHANGE` is the only value. If any caller passes `AgentMode.LOOP` or the string `"loop"`, `parse_agent_mode` raises at runtime. No callers in source code use the old default positionally (the default was `"loop"` in `set_models.py` and `agent_mode=AgentMode.LOOP` in tui.py). After updating both sites, there are no live uses of `AgentMode.LOOP`. Mitigation: grep for `AgentMode.LOOP` and `"loop"` in the -a context before closing the change.
- **Claude wizard UX expansion**: `CLAUDE_WIZARD_AGENTS` growing from 3 to 8 agents means the Claude wizard now shows 8 agents. This is a noticeable UX difference but is correct behavior per the change spec. No additional code change needed beyond updating the constant.
- **Copilot/Claude install now installs only change agents**: Users who previously used the loop workflow via Copilot or Claude will have loop agents removed on next `uninstall + install`. The install manifest records what was installed; users can uninstall cleanly. No migration needed, but this should be noted in the README update.
- **Override store compatibility**: Existing `~/.ai-harness/overrides.json` files may contain keys for `explorer`, `implementor`, `validator`, `loop-orchestrator`. These stale keys are benign — `get_agent_meta` will never be called for them after removal, and `write_override_store` deep-merges over the existing store without removing old keys. Users with stale override entries will see them remain in `overrides.json` until they manually clean the file. This is acceptable behavior.
- **ADR retention vs removal**: `docs/adr/0003-loop-pr-prd-linking.md`, `0007-loop-worktree-isolation.md`, `0008-copilot-loop-agents-native-model.md` describe the loop set in present tense. They should receive a deprecation notice (one-line header) rather than being deleted, to preserve the decision record. The scope says "remove loop-set docs" — the implementor should decide whether ADRs count as "docs" or "historical records"; recommend keeping them with a deprecation note.
