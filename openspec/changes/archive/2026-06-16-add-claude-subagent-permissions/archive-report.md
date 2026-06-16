# Archive Report: add-claude-subagent-permissions

**Change**: add-claude-subagent-permissions
**Archived on**: 2026-06-16
**Verdict**: PASS WITH WARNINGS

## Summary

The Claude installer now manages `~/.claude/settings.json` `permissions.allow` rules: install computes the union of `tools:` declared by all staged sub-agents, maps them to permission rules, deep-merges missing rules into `permissions.allow` (idempotent), and records the change in a marker file. Uninstall reads the marker (or falls back to a 5-name heuristic if missing/corrupt) and removes only the rules it added. Backup of the original `settings.json` is created on first install and preserved across reinstalls and uninstalls.

## Specs merged

- `claude-permissions/spec.md` — 4 requirements, 14 scenarios (113 lines)

## Files changed

| File | Mode | Final LOC | Notes |
|------|------|-----------|-------|
| `src/ai_harness/artifacts/installers/permissions.py` | new | 262 | Deep module: 3 public + 5 private functions + 2 constants |
| `src/ai_harness/artifacts/installers/claude.py` | modify | +36 / -2 | `_install_permissions` / `_uninstall_permissions` wrappers + 2 call sites |
| `tests/test_permissions.py` | new | 617 | 38 unit tests across 12 test classes |
| `tests/test_install.py` | modify | +30 | Integration test for install writes 5 rules + marker + backup |
| `e2e/test_harness_lifecycle.py` | modify | +81 | E2E `_assert_claude_permissions` helper + install/uninstall assertions |
| `openspec/specs/claude-permissions/spec.md` | new | 113 | The merged canonical spec |

**Total**: 298 production LOC, 728 test LOC

## Test results at archive time

- `uv run pytest`: 178 passed, 0 failures
- `uv run pytest --cov=ai_harness`: permissions.py 96%, claude.py 97%
- `e2e/docker-test.sh`: All categories passed

## Pre-archive cleanup

- Fixed misleading comment in `permissions.py:244` (was: "only delete on non-fallback success or leave it"; now reflects the actual unconditional marker cleanup behavior). Comment-only change; 47/47 tests still pass.

## Verify warnings status

| Warning | Status |
|---------|--------|
| 1. Test code overage (617 vs 150-180 LOC) | Accepted — additional coverage is valuable; user approved pre-archive |
| 2. Extra private helper `_parse_frontmatter_tools` and constant `_MANAGED_RULE_NAMES` | Accepted — both internal, no API leak |
| 3. Comment-code mismatch in `_remove_managed_rules` | **Resolved** — comment fixed pre-archive |

## Final verdict

PASS WITH WARNINGS, warnings 1 and 2 accepted, warning 3 resolved.

## Open follow-ups (optional)

- Test code overage (warning 1) could be addressed by trimming `test_permissions.py` to ~250 LOC. Not required.
- The pre-flight budget was upgraded from C1=400 to C2=800 mid-flight; consider formalizing the TDD test code scaling factor in future estimates (3-4x the spec scenario count).

## Git status (for the user to commit)

The working tree is dirty. The following files are ready to commit:

```
 M e2e/test_harness_lifecycle.py
 M src/ai_harness/artifacts/installers/claude.py
 M tests/test_install.py
?? openspec/changes/archive/2026-06-16-add-claude-subagent-permissions/
?? openspec/specs/
?? src/ai_harness/artifacts/installers/permissions.py
?? tests/test_permissions.py
```

## Next steps for the user

1. Review the diff
2. Run `git add -A` to stage all changes
3. Commit with a conventional message (e.g., `feat: add claude subagent permissions via settings.json allow-rules`)
4. Push and open a PR
