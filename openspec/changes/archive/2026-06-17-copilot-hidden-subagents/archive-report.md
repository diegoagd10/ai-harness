# Archive Report: copilot-hidden-subagents

## Verdict Acknowledged
PASS (from verify-report.md)

## What Was Archived
- **Spec merged**: `openspec/specs/agent-clis-installer/spec.md` upgraded v2 → v3
  - 9 new requirements added (8 ADDED + Copilot Model Pinning)
  - 1 requirement modified (Per-Provider Metadata — adds Copilot serializer + scenario)
  - 28/28 spec scenarios covered by tests
- **Change folder moved**: `openspec/changes/copilot-hidden-subagents/` → `openspec/changes/archive/2026-06-17-copilot-hidden-subagents/`

## Production Artifacts Shipped
- `src/ai_harness/artifacts/installers/frontmatter.py` — new `copilot_frontmatter()` pure function
- `src/ai_harness/artifacts/installers/copilot.py` — `_METADATA` with per-agent `model` + orchestrator `agents:` allowlist; `.agent.md` extension; `agent` tool alias on orchestrator
- `tests/test_copilot_installer.py` — 19 unit tests (11 new for this change), all green
- `e2e/test_copilot_cli_lifecycle.py` — `.agent.md` suffix handling, key-order assertions, SSoT assertions, all green
- `openspec/changes/copilot-hidden-subagents/` → `openspec/changes/archive/2026-06-17-copilot-hidden-subagents/` — full SDD history (proposal, spec, design, tasks, apply-report, verify-report)

## Metrics
- Tasks: 18/18 complete
- Tests: 273 passed, 0 failed
- Ruff: clean
- E2E: passed in Docker
- Cross-CLI regression: none
- Estimated changed lines: ~315 (within 800-line budget)
- Review Workload Forecast risk: Low

## Notable Decisions
- **VS Code `agents:` field** (declarative sub-agent allowlist) is the Copilot equivalent of OpenCode's `permission.task`. Discovered mid-design by user correction; canonical reference is the VS Code custom-agents doc (which the Copilot custom-agents doc references for `.agent.md` file structure).
- **Model strings** are the display names from https://docs.github.com/en/copilot/reference/ai-models/supported-models: `GPT-5 mini` and `Claude Haiku 4.5`. Lived in `_METADATA` (single source of truth), not in the serializer.
- **Single source of truth**: `_SUBAGENT_NAMES` drives (1) the hook's `preToolUse[0].allow`, (2) the orchestrator's `agents:` frontmatter, and (3) the set of `user-invocable: false` agent ids. The SSoT test asserts all three are equal.
- **Pure serializer**: `copilot_frontmatter(metadata)` is a pure function. The decision to emit `agents:` is driven by `metadata.get("agents")` only, not by id-specific branches.
- **Archive applied cleanly**: The delta spec (v2→v3) merged the changelog, replaced the modified "Per-Provider Metadata" requirement, and appended 9 new Copilot-specific requirements. Purpose section preserved verbatim. All 28 scenarios from the original v2 spec plus the 9 new requirements' scenarios are present.

## Follow-ups (for the next change, not this one)
- Quarterly audit of model display names against the supported-models page (the YAML value for `model:` is the display name with a space; if GitHub ever changes it, the snapshot tests will fail and the constants need updating).
- If the Copilot CLI / cloud agent does NOT honor the `agents:` field at runtime, the `sdd-pre-tool-use.json` hook is the safety net. No further action needed unless we observe drift.
- If a future Copilot release exposes a more granular mechanism for agent scoping, the design is well-positioned to adopt it (the serializer is pure and the allowlist is a single list constant).
