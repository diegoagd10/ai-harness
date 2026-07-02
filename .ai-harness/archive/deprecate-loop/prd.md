# PRD — deprecate-loop

## Intent

The loop agent set (loop-orchestrator, explorer, implementor, validator) has been superseded by the change-orchestrator workflow. The harness must remove every loop artifact — resources, registry entries, wizard vocabulary, CLI options, tests, and documentation — so that only the change agent set remains. Users who install or configure the harness after this change interact exclusively with change agents.

## Scope

### In

- Delete all 5 files under `src/ai_harness/resources/loop-agent/` (explorer.md, implementor.md, loop-orchestrator.md, validator.md, _result-contract.md).
- Remove `AgentMode.LOOP`; collapse `AgentMode` to a single-member `CHANGE` enum. Remove `OPENCODE_WIZARD_AGENTS` constant and `opencode_wizard_agents()` function from `pure.py`.
- Expand `CLAUDE_WIZARD_AGENTS` to the full change agent set: all 8 change subagents plus change-orchestrator (9 agents total).
- Update `renderers.py`: remove `"loop-agent"` from `_AGENT_RESOURCE_DIRS`; remove four loop entries from `_AGENT_META`; rename `_discover_loop_agents` to `_discover_agents`.
- Update `set_models.py`: change `-a/--agent` default from `"loop"` to `"change"`; remove help text and inline comments referencing `"loop"` as a valid value.
- Docstring-only updates in `operations.py` and `worktree.py`.
- Update `README.md`, `CONTEXT.md`, and project `CLAUDE.md`: remove loop-workflow prose, loop agent references, loop-label triage instructions, and loop-install descriptions.
- Add a deprecation/superseded header to ADRs 0003, 0007, and 0008; do not delete them.
- Update `tests/test_renderers.py`, `tests/test_install.py`, `tests/test_set_models.py`, and `e2e/e2e_test.sh` to reflect removed loop artifacts, renamed discovery function, and updated file-count baselines.

### Out

- Retiring or deleting the `loop` GitHub label.
- Migration tooling: `uninstall + install` is the user migration path; no new CLI command or script for migrating existing loop agent files.
- Changes to `src/ai_harness/resources/skills/to-design/SKILL.md` (its "loop" mention is unrelated to the loop agent set).
- Deleting loop ADRs 0003, 0007, 0008 (retained with deprecation headers only).
- Decomposing this change into sub-changes.

## Capabilities

- **C-1 Loop resource purge**: The `src/ai_harness/resources/loop-agent/` directory and all 5 prompt files are deleted; `_AGENT_RESOURCE_DIRS`, `_AGENT_META`, and the internal discovery function in `renderers.py` carry no loop entries and no loop-specific naming.
- **C-2 Install deploys change agent set**: `ai-harness install -c claude` and `ai-harness install -c copilot` install the 9 change agents (8 subagents + change-orchestrator skill) instead of the previous loop set; install file counts and CLI output strings update to the new baseline.
- **C-3 set-models configures change agents**: `ai-harness set-models -o <cli>` writes model configuration for the full change agent set; `CLAUDE_WIZARD_AGENTS` covers all 9 change agents; the Claude wizard presents all 9 agents to the user.
- **C-4 --agent defaults to change, rejects loop**: `-a/--agent` on `set-models` is optional, defaults to `"change"`, and raises `typer.BadParameter` when given `"loop"`; `AgentMode` has exactly one valid member (`CHANGE`).

## Approach

Execute the exploration plan in the documented order:

1. Delete `src/ai_harness/resources/loop-agent/` (5 files).
2. Update `renderers.py` — remove loop from `_AGENT_RESOURCE_DIRS` and `_AGENT_META`; rename `_discover_loop_agents` to `_discover_agents` and fix all internal call sites.
3. Update `pure.py` — collapse `AgentMode` to one member; remove `opencode_wizard_agents`; expand `CLAUDE_WIZARD_AGENTS` to 9 change agents.
4. Update `tui.py` — remove `opencode_wizard_agents` import; simplify `run_wizard` to always use `opencode_change_agents()`; fix `agent_mode` defaults and all loop-referencing docstrings.
5. Update `set_models.py` — change `-a` default to `"change"`, strip loop references from help text and comments.
6. Update `operations.py` and `worktree.py` — docstrings only.
7. Update tests: `test_renderers.py`, `test_install.py`, `test_set_models.py`, `e2e/e2e_test.sh`.
8. Update docs: `README.md`, `CONTEXT.md`, project `CLAUDE.md`.
9. Add deprecation headers to ADRs 0003, 0007, 0008.

All quality gates from CODING_STANDARDS.md must pass: ruff format, ruff check, pylint duplicate-code, pytest, and e2e (required because install/uninstall behavior changes).

## Affected Areas

- `src/ai_harness/resources/loop-agent/` — deleted (5 files, 543 lines)
- `src/ai_harness/modules/wizard/pure.py` — AgentMode, constants, CLAUDE_WIZARD_AGENTS
- `src/ai_harness/modules/wizard/tui.py` — run_wizard, agent_mode defaults, imports, docstrings
- `src/ai_harness/modules/harness/renderers.py` — registry constants, discovery function rename
- `src/ai_harness/commands/set_models.py` — --agent default and help text
- `src/ai_harness/modules/harness/operations.py` — docstrings
- `src/ai_harness/modules/harness/worktree.py` — module docstring
- `tests/test_renderers.py` — path lists, loop-specific tests removed, discovery import updated
- `tests/test_install.py` — constants, file-count assertions, override agent key
- `tests/test_set_models.py` — AgentMode tests, opencode_wizard_agents call sites replaced
- `e2e/e2e_test.sh` — override test updated from implementor to change-implementor
- `README.md`, `CONTEXT.md`, project `CLAUDE.md` — loop prose removed
- `docs/adr/0003-loop-pr-prd-linking.md`, `docs/adr/0007-loop-worktree-isolation.md`, `docs/adr/0008-copilot-loop-agents-native-model.md` — deprecation headers added

## Risks

- **Test blast radius undercount** — `test_set_models.py` is 3693 lines with approximately 12–15 `opencode_wizard_agents()` call sites. Any missed swap silently validates the wrong agent set. Mitigation: grep for `opencode_wizard_agents` before marking implementation complete.
- **`_discover_loop_agents` rename** — imported by name in `tests/test_renderers.py` (line 22). Rename in `renderers.py` without updating the test import breaks the entire test module at collection time. Mitigation: grep for `_discover_loop_agents` across the full test surface before closing.
- **`AgentMode` single-member enum** — any remaining call site passing `AgentMode.LOOP` or the string `"loop"` raises at runtime. Mitigation: grep for `AgentMode.LOOP` and the string `"loop"` in the `--agent` context across source and tests before closing.
- **Claude wizard UX expansion** — `CLAUDE_WIZARD_AGENTS` growing from 3 to 9 agents is a noticeable UX change; it is intentional per scope but must be reflected in the README update.
- **Stale override store entries** — existing `~/.ai-harness/overrides.json` files may reference `explorer`, `implementor`, `validator`, or `loop-orchestrator` as keys. These become benign orphans after removal; no migration is needed, and cleanup is out of scope.
- **e2e override test** — `test_override_updates_installer_section` injects an `implementor` override and verifies `implementor.md`; this must be updated to use `change-implementor`. If missed, the e2e suite fails.

## Rollback Plan

Revert the branch. No data migrations are performed, so a revert restores all loop resources and references. Users who ran `ai-harness install` between deploy and rollback can re-run `uninstall + install` to restore loop agents from the reverted source.

## Dependencies

- The change-orchestrator agent set (`src/ai_harness/resources/change-agent/`) must already be present in the repository; the exploration confirms it is. No new resources are introduced.
- No new Python dependencies.
- e2e requires Docker for the install/uninstall lifecycle tests.

## Success Criteria

- **C-1**: `src/ai_harness/resources/loop-agent/` does not exist. Grep for `"loop-orchestrator"`, `"explorer"`, `"implementor"`, `"validator"` in `renderers.py` returns no hits in `_AGENT_RESOURCE_DIRS` or `_AGENT_META`. All quality gates pass.
- **C-2**: `ai-harness install -c claude` reports 15 installed files; `ai-harness install -c copilot` reports 21 files. No loop agent file appears in any install manifest. `test_install.py` passes with updated count assertions and no loop agent name constants.
- **C-3**: `CLAUDE_WIZARD_AGENTS` contains exactly 9 change agents. `ai-harness set-models -o claude` wizard presents 9 agents. `test_set_models.py` passes with all `opencode_wizard_agents()` call sites replaced by `opencode_change_agents()`.
- **C-4**: `ai-harness set-models` with no `-a` flag completes without error using `"change"` as the default. `ai-harness set-models -a loop` exits non-zero with a `BadParameter` message that does not name `"loop"` as valid. `AgentMode` has exactly one member. The `test_parse_agent_mode` tests pass with `"loop"` as an invalid input.
