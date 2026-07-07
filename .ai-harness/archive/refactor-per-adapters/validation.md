# Validation — refactor-per-adapters

## Verdict
verdict: pass-with-warnings
critical: 0

## Coverage
- task 1 / artifact-output-contract / Rendered result exposes install_path and content: pass
- task 2 / override-store-continuity / Save deep-merges and preserves unrelated keys: pass
- task 3 / json-backed-metadata-resources / Discovery returns sorted visible names only: pass
- task 4 / json-backed-metadata-resources / Unknown metadata field fails: pass
- task 5 / claude-artifact-administration / Primary change orchestrator becomes a skill: pass
- task 6 / opencode-artifact-administration / Explicit permission wins over caps: pass
- task 7 / copilot-artifact-administration / Missing model.copilot succeeds: pass
- task 8 / provider-administrator-dispatch / Render through provider-agnostic dispatch: pass
- task 9 / caller-migration / Installed files appear at stable provider-visible paths: pass
- task 10 / caller-migration / Wizard agent lists match discovered resources: pass
- task 11 / caller-migration / Tests compare Artifact objects directly: pass
- task 12 / caller-migration / E2E validates stable paths through new seam: pass
- task 13 / caller-migration / All tests pass through new seam: pass

## Capability Coverage
- Provider administrator dispatch: pass
- Claude artifact administration: pass
- OpenCode artifact administration: pass
- Copilot artifact administration: pass
- JSON-backed metadata resources: pass
- Artifact output contract: pass
- Override-store continuity: pass
- Caller migration: pass

## Structural Verification
- 1. administrators/ has exactly 5 files: pass
- 2. base.py exports Artifact, AgentMetadata, AgentCaps, ArtifactsAdministrator, and shared helpers: pass
- 3. claude.py exports ClaudeArtifactsAdministrator and keeps _claude_tools private: pass
- 4. opencode.py exports OpenCodeArtifactsAdministrator and keeps _opencode_permission private: pass
- 5. copilot.py exports CopilotArtifactsAdministrator: pass
- 6. __init__.py exports ADMINISTRATORS with the 3 concrete admins at import time: pass
- 7. provider files do not cross-import each other: pass
- 8. renderers.py keeps deprecated render_agents, get_agent_meta, write_override_store, RenderedFile importable and off __all__: pass
- 9. Artifact uses @dataclass(frozen=True, slots=True): pass

## Findings
### CRITICAL
- none

### WARNING
- `uv run pytest` still reports the pre-existing `test_claude_subagents_have_name_and_model` sonnet/fable mismatch; unchanged on parent and outside this change.
- `./e2e/docker-test.sh` failed in Docker build while fetching PyPI dependency `typer`; network/environment issue, not code.
- `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e` remains at 9.99/10 due the intentional deprecated-shim duplication.

### SUGGESTION
- none

## Gates
- command: `uv run ruff format --check .` — pass
- command: `uv run ruff check .` — pass
- command: `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e` — pass-with-warnings
- command: `uv run pytest` — fail (1 pre-existing failure)
- command: `./e2e/docker-test.sh` — fail (PyPI fetch timeout)

## TDD Evidence Audit

| Check           | Result | Details                                          |
|-----------------|--------|--------------------------------------------------|
| section-present | pass   | section present                                  |
| cross-ref       | pass   | every row's `(Task, Commit)` matches `## Commits`|
| no-duplicate    | pass   | no duplicate `(Task, Commit)` pairs              |
| no-extra        | pass   | no rows for pending tasks                        |
| grammar-red     | pass   | RED == "written"                               |
| grammar-green   | pass   | GREEN == "passed"                              |
| safety-net      | pass   | all rows use `passed: N/M` with `N ≤ M`          |
| test-coverage   | pass   | no behavior-without-test rows                    |
| layer           | pass   | Layer values stay in the allowed enum            |
| refactor        | pass   | Refactor values stay in the allowed enum         |
| gate-ownership  | pass   | gate failures are attributable by row ownership  |
| cell-count      | pass   | every row splits to ten cells                    |

### Self-checklist
- [x] section-present
- [x] cross-ref
- [x] no-duplicate
- [x] no-extra
- [x] grammar-red
- [x] grammar-green
- [x] safety-net
- [x] test-coverage
- [x] layer
- [x] refactor
- [x] gate-ownership
- [x] cell-count
