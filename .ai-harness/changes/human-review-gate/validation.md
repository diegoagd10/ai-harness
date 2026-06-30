# Validation — human-review-gate

## Verdict
verdict: fail
critical: 2

## Coverage
- task 1 / review-checkpoint-before-implementation / Scenario: Complete artifacts trigger review wait: pass
- task 1.1 / review-checkpoint-before-implementation / Scenario: Implementor is not launched before review: pass
- task 1.2 / review-checkpoint-before-implementation / Scenario: Human confirms continuation; Scenario: Ambiguous response does not approve; Scenario: Review prompt is actionable: pass
- task 1.3 / review-checkpoint-before-implementation / Scenario: Resume after session gap: pass
- task 1.4 / review-checkpoint-before-implementation / Scenario: Tasks change after review request; Scenario: Design changes after approval; Scenario: Approved artifacts stay stable: pass
- task 1.5 / review-checkpoint-before-implementation / Scenario: Parent split continues planning flow: pass
- task 1.6 / review-checkpoint-before-implementation / Scenario: Missing tasks block before review: pass
- task 2 / documentation-alignment / Scenario: Maintainer reads flow docs: pass
- task 2.1 / documentation-alignment / Scenario: Maintainer reads flow docs: pass
- task 2.2 / documentation-alignment / Scenario: Prompt-only resume is documented: pass
- task 2.3 / documentation-alignment / Scenario: Maintainer evaluates status changes: pass
- task 2.4 / documentation-alignment / Scenario: Parent Change flow is maintained: pass
- task 3 / prompt-contract-coverage / Scenario: Gate wording present: pass
- task 3.1 / prompt-contract-coverage / Scenario: Gate wording present: pass
- task 3.2 / prompt-contract-coverage / Scenario: Confirmation requirement visible: pass
- task 3.3 / prompt-contract-coverage / Scenario: Gate wording removed: pass
- task 3.4 / prompt-contract-coverage / Scenario: Body-only gate; Scenario: Metadata changes with prompt semantics: pass

## Findings
### CRITICAL
- `HOME=/tmp/opencode rtk uv run pytest` fails: `tests/test_install.py::test_discover_loop_agents_excludes_underscore_files` expects `opencode_change_agents()` order that does not match `_discover_loop_agents()`, and `tests/test_worktree.py` fails its git-commit setup under `/tmp/opencode` because required git identity is missing.

### WARNING
- none

### SUGGESTION
- none

## Gates
- command: `ai-harness task-list -c human-review-gate` → all tasks done
- command: `uv run ruff format --check .` → pass
- command: `uv run ruff check .` → pass
- command: `uv run pylint --disable=all --enable=duplicate-code --recursive=y ./src ./tests ./e2e` → pass
- command: `HOME=/tmp/opencode rtk uv run pytest` → fail (10 failures)
- command: `./e2e/docker-test.sh` → not run (diff does not touch e2e/ or install/uninstall behavior)
