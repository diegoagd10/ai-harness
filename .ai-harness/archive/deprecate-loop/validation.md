# Validation — deprecate-loop

## Verdict
verdict: pass-with-warnings
critical: 0

## Coverage
- task 1 / spec c1-loop-resource-purge / subtasks 1.1-1.3: pass
- task 1 / spec c2-install-deploys-change-agent-set / subtasks 1.4-1.6: pass
- task 2 / spec c3-set-models-configures-change-agents / subtasks 2.1-2.3: pass
- task 3 / spec c4-agent-flag-defaults-change-rejects-loop / subtasks 3.1-3.3: pass
- task 4 / spec c1-loop-resource-purge / subtasks 4.1-4.4: pass-with-warnings
- task 5 / spec c1-loop-resource-purge / subtasks 5.1-5.3: pass

## Findings
### CRITICAL
- none

### WARNING
- `README.md` still links to `docs/adr/0008-copilot-loop-agents-native-model.md`; that is a lingering historical loop reference, though it points at a retained superseded ADR.

### SUGGESTION
- none

## Gates
- command: `uv run pytest` — pass (534 passed)
- command: `uv run ruff format --check .` — pass
- command: `uv run ruff check .` — pass
- command: `RUN_FULL_E2E=1 ./e2e/docker-test.sh` — pass (Tier 1 43/43, Tier 2 30/30)
