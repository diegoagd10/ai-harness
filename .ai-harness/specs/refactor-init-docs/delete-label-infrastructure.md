# Spec — delete-label-infrastructure

## Purpose

The pre-refactor `ai-harness init` carried a third job — creating the
loop's GitHub labels (`ready-for-agent`, `loop`) via the `gh` CLI. That
job leaves the init surface entirely. This spec deletes the source and
test files that drove it and prunes the package re-exports so no in-tree
consumer can accidentally import a removed symbol.

A repo-wide grep MUST return zero matches for the deleted symbols after
this change lands. The cleanup must be atomic: deleting `labels.py`
without updating `__init__.py` would leave `from
ai_harness.modules.harness import LabelResult` raising `ImportError`
in a way that's hard to attribute — both must move together.

## Non-goals

- No deprecation shim — `LabelResult` and `ensure_labels` are deleted
  outright, not re-exported as deprecated.
- No new label-related capability introduced in their place — the
  responsibility leaves `init`. Any user who needs those labels must
  create them themselves (out of scope here).
- No removal of `uninstall_for_agent_clis`, `install_for_agent_clis`,
  `re_render_for_agent_clis`, `InstallManifest`, `InitResult`,
  `init_repo`, `AgentCli`, or any of the change / tasks / worktree
  re-exports — those are unrelated.

## Requirements

### Requirement: source and test files removed

The system MUST remove `src/ai_harness/modules/harness/labels.py`
and `tests/test_labels.py` from the repository.

#### Scenario: files no longer exist
GIVEN the refactor has been merged
WHEN `ls src/ai_harness/modules/harness/labels.py` is run
THEN the shell reports "No such file or directory"
AND `ls tests/test_labels.py` reports the same.

### Requirement: package re-exports tightened

The system MUST remove the `labels` import from
`src/ai_harness/modules/harness/__init__.py` and MUST remove
`LabelResult` and `ensure_labels` from that module's `__all__`.

#### Scenario: package surface is honest
GIVEN the refactor has been merged
WHEN Python evaluates `from ai_harness.modules.harness import LabelResult`
THEN an `ImportError` is raised
AND evaluating `from ai_harness.modules.harness import ensure_labels`
raises an `ImportError`
AND evaluating `from ai_harness.modules.harness import InitResult, init_repo`
succeeds (these survive).

### Requirement: zero in-tree references

The system MUST leave no in-tree reference to the deleted symbols.
A repo-wide search for `LabelResult`, `ensure_labels`,
`created_labels`, `label_warnings`, `_AI_HARNESS_START`,
`_AI_HARNESS_END`, `wrote_labels_policy`, `labels_policy_targets`,
or `no_agent_doc` MUST return no matches in source or test code
(behaviour-test fixtures excepted; none are expected to remain).

#### Scenario: post-merge search is empty
GIVEN the refactor has been merged
WHEN `rg -n "LabelResult|ensure_labels|wrote_labels_policy|labels_policy_targets|created_labels|label_warnings|_AI_HARNESS_START|_AI_HARNESS_END|no_agent_doc"` is run over the repo
THEN no matches are reported (the deletion targets themselves have
been removed, so they no longer contain those identifiers).

### Requirement: removed symbols also gone from `operations.py`

The system MUST drop the `labels` import from
`src/ai_harness/modules/harness/operations.py` and MUST remove
the `ensure_labels` call from `init_repo`.

#### Scenario: operations module is label-free
GIVEN the refactor has been merged
WHEN `init_repo` is called on a repo root
THEN no `subprocess` invocation targeting `gh` is performed
(no fixture is needed to assert this — the `gh` binary may not exist
in the test environment, and the result is the absence of any related
warning on stderr).
