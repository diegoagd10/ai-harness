# Archive Report: copilot-cli-sdd-adapter

## Change Summary
- **Change**: copilot-cli-sdd-adapter
- **Date archived**: 2026-06-16
- **Verdict**: PASS
- **Tasks completed**: 19/19
- **Tests**: 150/150 pass, e2e invoke pass, docker e2e pass
- **Coverage**: 96% global, copilot.py 90%

## What shipped

Added a full SDD adapter for GitHub Copilot CLI under `src/ai_harness/resources/agent-clis/copilot-cli/`, with 16 agents (1 orchestrator + 8 phase + 3 JD + 4 reviewers), JSON hooks, generic-ified shared prompts, and `CopilotInstaller` extensions following the Claude composition pattern.

## Files Changed
- New: `src/ai_harness/resources/agent-clis/copilot-cli/` (16 agent `.md` files + 1 hook JSON)
- New: `docs/agents/copilot/README.md` (adapter narrative)
- New: `e2e/test_copilot_cli_lifecycle.py` (~280 lines)
- New: `tests/test_copilot_installer.py` (11 unit tests, ~395 lines)
- Modified: `src/ai_harness/artifacts/installers/copilot.py` (+162 lines for compose-at-install + validation)
- Modified: `src/ai_harness/artifacts/catalog.py` (added `.copilot/skills` to SKILLS_TARGET_DIRS)
- Modified: `src/ai_harness/resources/prompts/sdd/sdd-*.md` (9 files generic-ified)
- Modified: `README.md` (added "GitHub Copilot CLI" section)
- Modified: `pyproject.toml` (moved pyyaml from dev to runtime deps)
- Modified: `e2e/tasks.py` (added copilot-cli-lifecycle invoke task)
- Modified: `tasks.py` (exposed copilot-cli-lifecycle at root)
- Modified: `tests/test_copilot_installer.py::_make_catalog_root` (test helper updated to match production hook structure)

## Specs Archived
- `specs/agent-clis-copilot-cli/spec.md` (NEW)
- `specs/cli-sdd/spec.md` (MODIFIED)
- `specs/prompts-sdd/spec.md` (MODIFIED)

Per project convention, specs live ONLY in the change's archive folder and are NOT promoted to `openspec/specs/`.

## Key Decisions
- Followed Claude adapter pattern (mixed frontmatter-only for SDD phases + frontmatter+inline-body for JD/reviewer)
- `ComposedFileArtifact` reused (no new abstraction)
- Hook allowlist omits dead `sdd-init`/`sdd-onboard` entries
- Frontmatter omits `target` field (broader IDE coverage)
- `pyyaml` is a runtime dep because frontmatter validation runs at install time
- All 16 agents visible in `/agent` picker (no `hidden` flag in copilot-cli; documented UX gap)

## Open Risks
- Hook JSON schema unverified against real copilot-cli parser (public docs 404). Manual verification required before production use.
- `pyyaml` is now a runtime dep (was dev). Documented in apply-report.md.

## Followups
- None required for this change.
