# Spec — C-4 --agent Defaults to Change, Rejects Loop

## Purpose

Ensure that `AgentMode` is a single-member `StrEnum` containing only `CHANGE`, that
`-a/--agent` on `set-models` defaults to `"change"` when omitted, and that passing `"loop"`
raises a `typer.BadParameter` error with a clear message. No call site in source or tests
may reference `AgentMode.LOOP` or the string `"loop"` as a valid agent mode value.

---

## Requirements

### Requirement: `AgentMode` has exactly one member

The system MUST collapse `AgentMode` in `src/ai_harness/modules/wizard/pure.py` to a
single-member `StrEnum`: `CHANGE = "change"`. The `LOOP` member MUST be deleted.

#### Scenario: AgentMode has one member

GIVEN the `deprecate-loop` branch is applied
WHEN `list(AgentMode)` is evaluated in a Python REPL
THEN the result is `[<AgentMode.CHANGE: 'change'>]` — exactly one member

#### Scenario: AgentMode.LOOP is absent

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "AgentMode.LOOP\|LOOP = " src/ai_harness/modules/wizard/pure.py` is executed
THEN the command returns no matches

---

### Requirement: `parse_agent_mode` raises on `"loop"` input

The system MUST update `parse_agent_mode(raw: str) -> AgentMode` so that any input other than
`"change"` (case-sensitive) raises `ValueError` with a message that names only `"change"` as a
valid value. The error text MUST NOT mention `"loop"` as a valid option.

#### Scenario: "loop" input raises ValueError

GIVEN `parse_agent_mode` is called with `raw = "loop"`
WHEN the call is executed
THEN a `ValueError` is raised
AND the error message does NOT contain `"loop"` as a valid value

#### Scenario: "change" input returns AgentMode.CHANGE

GIVEN `parse_agent_mode` is called with `raw = "change"`
WHEN the call is executed
THEN `AgentMode.CHANGE` is returned without raising

#### Scenario: Error message contains "valid values: change"

GIVEN `parse_agent_mode` is called with any invalid value
WHEN the `ValueError` message is inspected
THEN it contains the substring `"valid values: change"` (derived from `AgentMode` members)

---

### Requirement: `set-models` surfaces `BadParameter` for `"loop"` input

The system MUST ensure that `src/ai_harness/commands/set_models.py` wraps the `ValueError` from
`parse_agent_mode` in `typer.BadParameter` when `-a loop` is supplied. The command MUST exit
non-zero and print a clear error message to stderr.

#### Scenario: `-a loop` exits non-zero

GIVEN `ai-harness set-models -o claude -a loop` is invoked
WHEN the command runs
THEN the exit code is non-zero (error)

#### Scenario: BadParameter message does not list "loop" as valid

GIVEN `ai-harness set-models -o claude -a loop` is invoked
WHEN stderr is inspected
THEN the output contains the word `"change"` as the valid value
AND does NOT contain `"loop"` as a valid option

---

### Requirement: `-a/--agent` defaults to `"change"` when omitted

The system MUST change the default value of the `-a/--agent` option in `set_models.py` from
`"loop"` to `"change"`. When the flag is omitted entirely, the command MUST behave as if
`-a change` was passed.

#### Scenario: Omitting -a uses change default

GIVEN `ai-harness set-models -o opencode` is invoked with no `-a` flag
WHEN the command completes (or launches wizard)
THEN the command targets the change agent set and exits without a BadParameter error

#### Scenario: Default value in source

GIVEN the `deprecate-loop` branch is applied
WHEN `grep 'default.*"loop"\|"loop".*default' src/ai_harness/commands/set_models.py` is executed
THEN the command returns no matches (old loop default is gone)

---

### Requirement: Help text names only "change" as valid

The system MUST remove all references to `"loop"` as a valid `-a` value from the help text and
inline comments in `set_models.py`. The updated help text MUST name only `"change"` as the valid
value for OpenCode.

#### Scenario: No loop reference in set_models help text

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "loop" src/ai_harness/commands/set_models.py` is executed
THEN the command returns no matches (no loop references remain in help text or comments)

---

### Requirement: TUI defaults updated to `AgentMode.CHANGE`

The system MUST update the default value of `agent_mode` in `run_wizard`, `run_claude_wizard`,
and `run_wizard_or_bail` in `src/ai_harness/modules/wizard/tui.py` from `AgentMode.LOOP` to
`AgentMode.CHANGE`.

#### Scenario: No AgentMode.LOOP default in tui.py

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "AgentMode.LOOP" src/ai_harness/modules/wizard/tui.py` is executed
THEN the command returns no matches

#### Scenario: AgentMode.CHANGE default present in tui.py

GIVEN the `deprecate-loop` branch is applied
WHEN `grep "AgentMode.CHANGE" src/ai_harness/modules/wizard/tui.py` is executed
THEN at least one match is found (default argument sites)

---

### Requirement: `test_set_models.py` validates `AgentMode` single-member semantics

The system MUST update `test_parse_agent_mode_accepts_loop_and_change` (rename and narrow it) so
that it asserts only `"change"` is accepted. The test MUST also assert that `"loop"` is now
invalid. `"LOOP"` and `"Loop"` cases MUST be removed from the uppercase-rejection test.

#### Scenario: "loop" treated as invalid in tests

GIVEN `test_set_models.py` is updated
WHEN `uv run pytest tests/test_set_models.py -k "parse_agent_mode"` is executed
THEN all `parse_agent_mode` tests pass
AND the test that previously accepted `"loop"` now asserts `"loop"` raises `ValueError`

#### Scenario: No LOOP or "Loop" in AgentMode test cases

GIVEN the `deprecate-loop` branch is applied
WHEN `grep '"LOOP"\|"Loop"\|AgentMode.LOOP' tests/test_set_models.py` is executed
THEN the command returns no matches

---

### Requirement: No residual `AgentMode.LOOP` references anywhere

The system MUST ensure that after all changes are applied, no source file or test file contains
`AgentMode.LOOP` or uses the string `"loop"` in a context that implies it is a valid agent mode.

#### Scenario: Global grep for AgentMode.LOOP

GIVEN the `deprecate-loop` branch is applied
WHEN `grep -r "AgentMode.LOOP" src/ tests/` is executed
THEN the command returns no matches

#### Scenario: pytest suite passes

GIVEN all `AgentMode` references are updated
WHEN `uv run pytest` is executed from the project root
THEN the entire test suite passes (exit code 0)
