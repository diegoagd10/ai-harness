# Spec — align-test-fixtures

## Purpose

The three test files that pin agent names — `tests/test_renderers.py`,
`tests/test_set_models.py`, `tests/test_install.py` — MUST be updated so
their expected-name lists, render-path basenames, frontmatter `name`
values, allowlist tuples, OpenCode permission dict keys, and substring
assertions reflect the new `change-*` names. The cardinality invariants
the tests pin (notably `len(names) == 13` and the
`test_opencode_change_agents_returns_expected_tuple` order) MUST be
preserved.

## Requirements

### Requirement: test_renderers expected names use the prefixed forms
The system MUST update every expected-name list, render-path basename,
frontmatter `name` expectation, prompt-content keyword assertion dict
key, allowlist tuple, and OpenCode `permission.task` dict key in
`tests/test_renderers.py` that previously referenced the bare agent
names to use the `change-*` form, and MUST NOT add, remove, or reorder
the entries — only their string content changes.

#### Scenario: render-path basenames are renamed
GIVEN `test_renderers.py` asserts on render-path basenames for the four
bare-named agents
WHEN the fixtures are updated
THEN every such assertion expects `change-design`, `change-propose`,
`change-specs`, or `change-tasks`
AND no assertion expects the bare `design`, `propose`, `specs`, or
`tasks` filename.

#### Scenario: frontmatter name expectations match the new stems
GIVEN the test reads each agent file and asserts on its frontmatter
`name`
WHEN the fixtures are updated
THEN the asserted `name` for the four renamed files equals the new stem
`change-design`, `change-propose`, `change-specs`, or `change-tasks`.

#### Scenario: keyword-contract dict keys are prefixed
GIVEN the prompt-content keyword contract test asserts on a dict keyed
by agent name
WHEN the fixtures are updated
THEN the four renamed keys carry the `change-*` form
AND the dict still has the same number of entries.

### Requirement: _discover_loop_agents invariant is preserved
The system MUST ensure that the test pinning
`_discover_loop_agents` still returns exactly thirteen names after the
rename, and that every returned name starts with `change-`.

#### Scenario: discovery still yields 13 prefixed names
GIVEN the on-disk templates are renamed
WHEN `_discover_loop_agents()` is invoked from the test
THEN `len(names) == 13`
AND every name in the returned list starts with `change-`.

### Requirement: test_set_models fixtures are aligned
The system MUST update the `opencode_change_agents()` tuple assertion
in `tests/test_set_models.py` so its four renamed entries carry the
`change-*` form in the same orchestrator-first order, and MUST leave the
`forbidden_prefixes` tuple as-is for this change (the wider list still
passes after the rename).

#### Scenario: wizard tuple assertion uses prefixed names
GIVEN the test currently asserts the bare-named wizard tuple
WHEN the fixture is updated
THEN the assertion expects the four `change-*` names in the same
orchestrator-first position
AND `change-orchestrator` remains the first element.

### Requirement: test_install fixtures are aligned
The system MUST update the `_CHANGE_SUBAGENT_NAMES` and
`_NATIVE_AGENT_NAMES` constants (or equivalent fixture lists) in
`tests/test_install.py` so the four renamed agents appear under their
new `change-*` names. No entry is added or removed.

#### Scenario: install fixture lists are renamed in place
GIVEN the install test enumerates agent names to install or to skip
WHEN the fixtures are updated
THEN the four renamed entries use `change-design`, `change-propose`,
`change-specs`, and `change-tasks`
AND no other entry is touched
AND both lists retain their original length.

### Requirement: full test suite stays green
The system MUST keep
`tests/test_renderers.py`, `tests/test_set_models.py`,
`tests/test_install.py`, and `tests/test_change.py` passing under
`pytest -x -q` after the rename.

#### Scenario: targeted pytest run is clean
GIVEN the rename and all fixture updates are applied
WHEN `pytest tests/test_renderers.py tests/test_set_models.py
tests/test_install.py tests/test_change.py -x -q` runs
THEN the command exits 0
AND no test is skipped or xfailed as a workaround.

### Requirement: no bare-name agent fixture string remains
The system MUST eliminate any fixture string of the form
`"design"`, `"propose"`, `"specs"`, or `"tasks"` referring to an agent
name from the three test files, with the optional exception of the
`forbidden_prefixes` tuple in `test_set_models.py` (kept as-is by
explicit scope decision).

#### Scenario: grep for bare names is empty in tests
GIVEN the fixtures are updated
WHEN `git grep -nE '"(propose|design|specs|tasks)"' tests/` runs
THEN the only matches, if any, are inside the `forbidden_prefixes`
tuple of `test_set_models.py`
AND no other test file contains a bare-name fixture string.