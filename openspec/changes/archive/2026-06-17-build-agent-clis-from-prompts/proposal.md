# Proposal: Build Agent CLIs from Prompts (Drop agent-clis/ Source Tree)

## Intent

Round 1 kept `agent-clis/<provider>/` as shim targets; installers wrote composed output there, **corrupting committed files**: 16 hardcoded `/tmp/pytest-of-...` paths in `opencode.json`, doubled `---` separators in inline agents. Fix: **delete `agent-clis/` entirely**. Installers build every artifact from canonical prompts + `_METADATA` + provider glue. No reads from, no writes to `agent-clis/`. This completes the architectural inversion.

## Scope

### In Scope
1. Delete all 37 files + 4 dirs under `agent-clis/{claude,copilot-cli,opencode}/`.
2. Build all artifacts in memory from `prompts/<ns>/<name>.md` + `_METADATA` dicts.
3. Install writes ONLY to user-facing paths. No source-path writes.
4. Retarget 5 e2e constants to `resources/generated/`. E2e logic frozen — constants only.
5. Installers write generated fixtures to `resources/generated/`, guarded by `os.access(os.W_OK)`.
6. Catalog drops `OPENCODE_JSON_SRC`.
7. Orchestrator Agent-variant `prompts/orchestrator/sdd-orchestrator-agent.md` kept for Claude.
8. New tests for build-from-code; existing shim tests inverted.

### Out of Scope
- Changing install layout, adding providers.
- Modifying e2e logic beyond 5 constant lines.
- `opencode/blocks/` and `opencode/plugins/` (deferred).

## Capabilities

### Modified Capabilities
- **agent-clis-installer**: Remove "E2E Shim." Replace with: build from canonical prompts only; no `agent-clis/` reads; generated fixtures at `resources/generated/`. Drop `OPENCODE_JSON_SRC`.
- **claude-permissions**: No functional change. Minor delta if `_METADATA` location shifts.

## Approach

Extend existing `_METADATA` dicts to cover every agent. Build `ComposedFileArtifact(frontmatter_text=..., body_source=...)`. OpenCode: assemble `opencode.json` in memory. Copilot: generate hook JSON from allowlist + deny-path constant. Add write-guarded `_write_fixtures`. Simplify `_prepare_composed_content` — drop `frontmatter_source`.

## Affected Areas

| Area | Impact |
|------|--------|
| `resources/agent-clis/` | Removed (37 files) |
| `installers/{opencode,claude,copilot}.py` | Modified |
| `artifacts/{catalog,manifest,installer}.py` | Modified |
| `e2e/test_harness_lifecycle.py` | 3 constant retargets |
| `e2e/test_copilot_cli_lifecycle.py` | 2 constant retargets |
| `tests/` (5 files) | Modified |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Read-only source blocks fixture writes | Low | `os.access(os.W_OK)` guard |
| Byte-equivalence drift | Med | Same code path for fixtures and install |
| Copilot deny paths desync | Low | Shared constant |

## Rollback Plan

`git revert`. Restore `agent-clis/` from git. Revert e2e constants + catalog.

## Dependencies

None — canonical prompts and `_METADATA` exist from Round 1.

## Open Questions

1. `opencode/blocks/` and `opencode/plugins/`: delete or preserve? → design.
2. Copilot hook `sdd-pre-tool-use.json`: generate in code or move as static? → recommends code-gen.
3. Fixture path: `resources/generated/` (gitignored) or `build/`? → design.

## Success Criteria

- [ ] No file under `agent-clis/` exists.
- [ ] `install --all` produces byte-identical output without reading `agent-clis/`.
- [ ] 5 e2e constants retargeted; `e2e/docker-test.sh` passes.
- [ ] `uv run pytest` passes — no regressions.
- [ ] No hardcoded `/tmp` paths in `opencode.json`.
- [ ] No doubled `---` in any artifact.
- [ ] Claude orchestrator built from `prompts/orchestrator/sdd-orchestrator-agent.md`.
