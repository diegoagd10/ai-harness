# Validation — prompt-e2e-red-tests

## Verdict
verdict: pass
critical: 0

## Coverage
- task 1 / spec tool-sequence-helper / scenario ordered tool sequence over a mixed stream: pass
- task 2 / spec e2e-assertions-helpers / scenario matches a bash tool_use that calls change-new: pass
- task 3 / spec cases-e2e-fixture-csv / scenario baseline counts are 0,0,0 for every fixture: pass
- task 4 / spec e2e-assertions-helpers / scenario helper's parity with _e2e_assertions is locked: pass
- task 5 / spec cases-e2e-fixture-csv / scenario in-container run.sh sees the new CSV: pass
- task 6 / spec runsh-e2e-group / scenario at least one failing RED row returns non-zero: pass
- task 7 / spec red-pytest-fixture-suite / scenario complete fixture OR-fence holds: pass (PROMPT_E2E_RED=1 produced the expected RED failure on the complete fixture; small and vague fixtures passed, default gate skipped cleanly)
- task 8 / spec host-dispatch-driver / scenario import graph is Docker-free: pass (default gate skipped cleanly; gate-on matched the current prompt behavior with the expected complete-fixture RED failure)
- task 9 / spec red-pytest-fixture-suite / scenario static tests always pass: pass

## Findings
### CRITICAL
- none

### WARNING
- none

### SUGGESTION
- none

## Gates
- ruff format: pass
- ruff check: pass
- pylint duplicate-code: pass
- pytest: pass
- e2e: not-run (not applicable; diff does not touch e2e/ or install/uninstall behavior)
