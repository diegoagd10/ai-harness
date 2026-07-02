# Spec — C-2 Install Deploys Change Agent Set

## Purpose

Ensure that `ai-harness install -c claude` and `ai-harness install -c copilot` install exactly the
9 change agents (8 subagents + `change-orchestrator` skill) and report the correct file counts.
No loop-agent file must appear in any install manifest after this change.

---

## Requirements

### Requirement: Claude install writes 15 files

The system MUST install exactly 15 files when `ai-harness install -c claude` is executed: 6 core
files + 8 change subagent files + 1 `change-orchestrator` skill file = 15.

#### Scenario: CLI output confirms 15 files

GIVEN a clean home directory with no prior harness install
WHEN `ai-harness install -c claude` is executed
THEN stdout contains `"15 file(s)"` and the exit code is 0

#### Scenario: No loop-agent file in Claude install output

GIVEN `ai-harness install -c claude` completes successfully
WHEN the install manifest or the written file paths are inspected
THEN no path contains `"loop-orchestrator"`, `"explorer"`, `"implementor"`, or `"validator"`
  as a standalone agent name (i.e., not prefixed by `change-`)

---

### Requirement: Copilot install writes 21 files

The system MUST install exactly 21 files when `ai-harness install -c copilot` is executed:
the 15 Claude files + 6 additional OpenCode/Copilot-specific files = 21.

#### Scenario: CLI output confirms 21 files

GIVEN a clean home directory with no prior harness install
WHEN `ai-harness install -c copilot` is executed
THEN stdout contains `"21 file(s)"` and the exit code is 0

#### Scenario: No loop-agent file in Copilot install output

GIVEN `ai-harness install -c copilot` completes successfully
WHEN the install manifest or written file paths are inspected
THEN no path contains `"loop-orchestrator"`, `"explorer"`, `"implementor"`, or `"validator"`
  as a standalone agent name

---

### Requirement: `test_install.py` constants reflect change-only agent set

The system MUST update `tests/test_install.py` so that:
- `_LOOP_AGENT_NAMES` constant is deleted.
- `_NATIVE_AGENT_NAMES` contains only the 9 change agents.
- `_CLAUDE_SUBAGENT_NAMES` contains only the 8 change subagents (no loop subagent names).
- `_CLAUDE_SKILL_NAME` is `"change-orchestrator"` (was `"loop-orchestrator"`).
- All file-count assertions use the updated baselines (Claude: 15, Copilot: 21, OpenCode: 9,
  OpenCode CLI output: `"15 file(s)"` and `"19 file(s)"` adjusted accordingly).

#### Scenario: No loop-agent names in test constants

GIVEN the `deprecate-loop` branch is applied
WHEN `grep -n "loop-orchestrator\|_LOOP_AGENT_NAMES\|\"explorer\"\|\"implementor\"\|\"validator\"" tests/test_install.py` is executed
THEN the command returns no matches on non-comment lines

#### Scenario: Updated file-count assertions compile and pass

GIVEN all file-count constants are updated
WHEN `uv run pytest tests/test_install.py` is executed
THEN the suite passes (exit code 0)

---

### Requirement: Override test uses a change-agent key

The system MUST update the override test(s) in `tests/test_install.py` that reference
`"implementor"` as an agent key and `implementor.md` as a file path. The test MUST be rewritten
to use a change agent (e.g., `"change-implementor"` and the corresponding
`change-implementor.md` path).

#### Scenario: Implementor override test references change-implementor

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "\"implementor\"" tests/test_install.py` is executed
THEN the command returns no matches (the old loop-agent key is gone)

#### Scenario: Change-implementor override test passes

GIVEN the override test uses `"change-implementor"` as the override key
WHEN `uv run pytest tests/test_install.py -k "override"` is executed
THEN the relevant test functions pass (exit code 0)

---

### Requirement: e2e override test uses a change-agent name

The system MUST update `e2e/e2e_test.sh` so that `test_override_updates_installer_section`
injects a `change-implementor` override (not `implementor`) and verifies `change-implementor.md`
is written rather than `implementor.md`. This function is in Tier 2 (`RUN_FULL_E2E=1`).

#### Scenario: e2e test references change-implementor

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "implementor" e2e/e2e_test.sh` is executed
THEN all matches are prefixed by `change-` (no bare `implementor` override key or path)

#### Scenario: e2e override test passes under Docker

GIVEN `RUN_FULL_E2E=1` and Docker is available
WHEN `./e2e/docker-test.sh` is executed
THEN `test_override_updates_installer_section` passes and the overall suite exits 0

---

### Requirement: Install test names reflect change-agent language

The system SHOULD rename any test function in `tests/test_install.py` whose name includes
`loop_agents` to use `change_agents` so that test names describe the actual behaviour being
verified.

#### Scenario: No loop_agents in test function names

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "def test_.*loop_agent" tests/test_install.py` is executed
THEN the command returns no matches
