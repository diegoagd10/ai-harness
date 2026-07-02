# Spec — C-3 set-models Configures Change Agents

## Purpose

Ensure that `CLAUDE_WIZARD_AGENTS` covers all 9 change agents, that the Claude wizard presents
all 9 agents to the user, and that `test_set_models.py` is updated to replace every
`opencode_wizard_agents()` call site with `opencode_change_agents()`.

---

## Requirements

### Requirement: `CLAUDE_WIZARD_AGENTS` contains exactly 9 change agents

The system MUST update `CLAUDE_WIZARD_AGENTS` in `src/ai_harness/modules/wizard/pure.py` to
contain exactly 9 entries: the 8 change subagents (`change-explorer`, `change-implementor`,
`change-validator`, `change-propose`, `change-specs`, `change-tasks`, `change-design`,
`change-archiver`) plus `change-orchestrator`. No loop subagent name (`explorer`, `implementor`,
`validator`) MUST appear in this tuple.

#### Scenario: Constant has 9 members

GIVEN `pure.py` is updated
WHEN `len(CLAUDE_WIZARD_AGENTS)` is evaluated in a Python REPL
THEN the result is `9`

#### Scenario: No loop subagent name in CLAUDE_WIZARD_AGENTS

GIVEN the `deprecate-loop` branch is applied
WHEN `python -c "from ai_harness.modules.wizard.pure import CLAUDE_WIZARD_AGENTS; print(CLAUDE_WIZARD_AGENTS)"` is executed
THEN the output contains none of `"explorer"`, `"implementor"`, `"validator"`,
  `"loop-orchestrator"` as standalone values (values not prefixed by `change-`)

---

### Requirement: `claude_wizard_agents()` accessor returns all 9 change agents

The system MUST ensure that `claude_wizard_agents()` returns the updated `CLAUDE_WIZARD_AGENTS`
tuple. The accessor's shape is unchanged; its contents change automatically when the constant
is updated.

#### Scenario: Accessor returns 9 agents

GIVEN `CLAUDE_WIZARD_AGENTS` is updated to 9 entries
WHEN `claude_wizard_agents()` is called
THEN it returns a tuple of length 9 whose entries all begin with `"change-"`

---

### Requirement: `opencode_wizard_agents` is deleted from `pure.py`

The system MUST delete both `OPENCODE_WIZARD_AGENTS` constant and `opencode_wizard_agents()`
function from `pure.py`. No alias or shim MUST replace them.

#### Scenario: Deleted symbol absent from pure module

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "opencode_wizard_agents\|OPENCODE_WIZARD_AGENTS" src/ai_harness/modules/wizard/pure.py` is executed
THEN the command returns no matches

---

### Requirement: `test_set_models.py` replaces all `opencode_wizard_agents()` call sites

The system MUST replace every call to `opencode_wizard_agents()` in `tests/test_set_models.py`
with `opencode_change_agents()`. The import of `opencode_wizard_agents` MUST also be removed.
No call site MUST be missed.

#### Scenario: No opencode_wizard_agents in test file

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "opencode_wizard_agents" tests/test_set_models.py` is executed
THEN the command returns no matches

#### Scenario: opencode_change_agents import present in test file

GIVEN all call sites are updated
WHEN `grep "opencode_change_agents" tests/test_set_models.py` is executed
THEN at least one match is found (the import and/or call sites)

---

### Requirement: Claude wizard presents 9 agents at runtime

The system MUST ensure that when `ai-harness set-models -o claude` launches the interactive
wizard, the wizard presents model and effort selection for all 9 change agents. This is validated
transitively through `test_set_models.py` tests that drive the wizard with the updated agent list.

#### Scenario: Wizard test suite passes with 9-agent list

GIVEN all `opencode_wizard_agents()` call sites in `test_set_models.py` are replaced by
  `opencode_change_agents()`
WHEN `uv run pytest tests/test_set_models.py` is executed
THEN the suite passes (exit code 0)

---

### Requirement: Re-render count test updated to 9

The system MUST update any test in `test_set_models.py` that asserts re-render file count.
The assertion SHOULD change from 13 (old loop+change total) to 9 (change agents only) wherever
the count reflects the discovered agent set size.

#### Scenario: Re-render count assertion uses 9

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "13" tests/test_set_models.py` is executed in the context of re-render count assertions
THEN no hardcoded `13` remains as a file count for agent renders

#### Scenario: Re-render test passes with updated count

GIVEN the count assertion is updated to 9
WHEN `uv run pytest tests/test_set_models.py -k "re_render"` is executed
THEN matching test functions pass (exit code 0)

---

### Requirement: `test_opencode_wizard_agents_includes_orchestrator_first` is removed

The system MUST remove the test function
`test_opencode_wizard_agents_includes_orchestrator_first` from `tests/test_set_models.py` because
it validates the deleted `opencode_wizard_agents()` function.

#### Scenario: Deleted test function is gone

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "test_opencode_wizard_agents_includes_orchestrator_first" tests/test_set_models.py` is executed
THEN the command returns no matches
