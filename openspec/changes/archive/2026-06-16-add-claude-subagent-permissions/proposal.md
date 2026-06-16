# Proposal: Claude Subagent Permissions via settings.json Allow-Rules

## Why

Claude Code background sub-agents fail silently ("I don't have Bash") because
the parent session's `~/.claude/settings.json` `permissions.allow` list is
missing `Bash`, `Read`, `Edit`, and `Write` rules. Per Claude Code docs,
background sub-agents inherit the parent's permission context and auto-deny any
tool that would otherwise prompt. The sub-agent frontmatter `tools:` fields are
already correct — the gap is session-level `permissions.allow` that the
installer does not currently manage.

## What Changes

### New Capabilities

- **`claude-permissions-merge`**: On **install**, the Claude installer SHALL
  compute the union of `tools:` frontmatter fields from all staged sub-agents
  AND the orchestrator SKILL.md; SHALL map tool names to permission rules
  (`Bash`, `Read`, `Edit`, `Write`, `Agent` — `Glob`/`Grep` SHALL be satisfied
  by a single `Read` rule); and SHALL deep-merge missing rules into
  `settings.json` `permissions.allow` without disturbing user-managed keys,
  formatting, or existing entries. The merge MUST be idempotent.

- **`claude-permissions-cleanup`**: The installer SHALL record added rules in
  `~/.claude/.ai-harness-managed-allow.json`. On **uninstall**, it MUST remove
  only those rules from `settings.json` `permissions.allow` and delete the
  marker. If the marker is missing or corrupt, uninstall MUST fall back to
  removing rules whose removal leaves the file valid.

- **`claude-config-location`**: The change MUST respect the `CLAUDE_CONFIG_DIR`
  environment variable when locating `settings.json`, falling back to
  `~/.claude/settings.json`.

- **`claude-settings-backup`**: Before modifying `settings.json`, the installer
  MUST back it up (suffix `.ai-harness-backup`), consistent with existing
  installer conventions in `src/ai_harness/artifacts/installer.py`.

### Modified Capabilities

None. This is new behavior layered on the existing Claude installer; no
existing spec-level behavior changes.

## Impact

| Area | File | Mode | Why |
|------|------|------|-----|
| Claude installer | `src/ai_harness/artifacts/installers/claude.py` | modify | Call permissions module during install/uninstall |
| Permissions module | `src/ai_harness/artifacts/installers/permissions.py` | **new** | Merge logic, marker management, tool-to-rule mapping |
| Unit tests | `tests/test_permissions.py` | **new** | Merge, idempotency, cleanup, fallback, tool mapping |
| Unit tests | `tests/test_install.py` | modify | Assert settings.json is produced after install |
| E2E suite | `e2e/test_harness_lifecycle.py` | modify | Assert settings.json permissions round-trip |

**Specs affected**: `openspec/specs/` does not exist. This change creates specs
for `claude-permissions-merge`, `claude-permissions-cleanup`,
`claude-config-location`, and `claude-settings-backup`.

**Public surface**: None. No new CLI flags, commands, or user-facing surface.

**Downstream consumers**: None depend on `settings.json` being untouched.

## Non-Goals / Out of Scope

- Will NOT modify `permissions.deny` or permission modes
- Will NOT introduce per-tenant or per-project permission systems
- Will NOT touch the OpenCode adapter or its sub-agent permissions
- Will NOT add a `doctor` subcommand

## Open Questions

None — ready for spec.

## Success Criteria

- After `ai-harness install` on a minimal settings.json, `permissions.allow`
  contains `Bash`, `Read`, `Edit`, `Write`, and `Agent`
- After `ai-harness uninstall`, `settings.json` is byte-equivalent to its
  pre-install state (excluding the deleted marker file)
- Running `ai-harness install` twice does not duplicate allow rules
- The change passes `uv run pytest` and adds test coverage for merge, marker,
  cleanup, and fallback paths
- E2E lifecycle suite asserts settings.json round-trip in fresh-install and
  reinstall scenarios

## Size Estimate

| Component | Est. lines | Uncertainty |
|-----------|-----------|-------------|
| `permissions.py` (new) | 120–150 | Medium |
| `claude.py` (integration) | 15–20 | Low |
| `test_permissions.py` (new) | 150–180 | Low |
| `test_install.py` (assertions) | 20–30 | Low |
| `e2e/test_harness_lifecycle.py` | 30–40 | Medium |
| **Total** | **335–420** | |
