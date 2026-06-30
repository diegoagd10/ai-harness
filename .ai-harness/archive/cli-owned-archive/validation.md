# Validation — cli-owned-archive

## Verdict
verdict: pass
critical: 0

## Coverage
- task 1 / spec archive-command / scenario Command is available: pass
- task 1 / spec structural-preflight / scenario Valid archive preflight: pass
- task 1 / spec transactional-archive-move / scenarios Specs promoted, Archived Change excludes specs subtree, Stale archive layout is not used, Failure while moving remaining Change, Failure while promoting specs: pass
- task 1 / spec machine-readable-failure-output / scenarios Successful archive uses terminal token only, Structural failure JSON, Invalid archive has no success output, Failed archive uses errors object only: pass
- task 2 / spec dedicated-archive-agent / scenarios Prompt resource present, Archiver executes CLI archive, Successful archive commit, Unrelated product dirtiness ignored, No duplicate commit on success, Command failure escalates, Success envelope, Blocked envelope, Renderer discovers archiver, Spawn allowlist includes archiver, Wizard vocabulary includes archiver: pass
- task 3 / spec terminal-archive-routing / scenarios Semantic gate blocks archive, Semantic gate passes archive candidate, Archive routed to archiver, Orchestrator does not own file moves, Archiver success ends flow, Archiver blocked result escalates, Rendered orchestrator contains archive route: pass

## Findings
### CRITICAL
- none

### WARNING
- none

### SUGGESTION
- none

## Gates
- `uv run pytest tests/test_change.py tests/test_renderers.py tests/test_install.py tests/test_set_models.py`: pass (372 passed)
