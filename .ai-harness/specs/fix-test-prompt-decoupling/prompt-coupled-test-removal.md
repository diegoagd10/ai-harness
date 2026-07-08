# Spec — Prompt-coupled test removal

## Purpose

Remove brittle renderer tests that lock prompt prose, command wording, result-envelope wording, or exact resource parity, while preserving adjacent coverage owned by other child changes.

## Requirements

### Requirement: Remove five named prompt-coupled tests
The system MUST remove only the five named prompt/resource-coupled tests from `tests/test_renderers.py`.

#### Scenario: Locked prose tests are absent
GIVEN `tests/test_renderers.py` after the change
WHEN the test definitions are inspected
THEN `test_change_agent_prompt_set_contains_expected_contract_keywords`, `test_change_archiver_prompt_runs_cli_command_and_commits_once`, `test_change_archiver_body_ignores_unrelated_product_dirtiness`, `test_change_archiver_result_envelope_includes_archive_commit_and_blocked_errors`, and `test_agent_metadata_has_one_json_file_per_change_agent_template` are not present.

#### Scenario: Adjacent child-change coverage remains
GIVEN renderer tests that cover shim deletion, import migration, or home isolation
WHEN the five named prompt-coupled tests are removed
THEN unrelated adjacent tests remain present and executable.

### Requirement: Avoid replacement prompt-prose assertions
The system MUST NOT replace the deleted tests with new assertions that inspect exact prompt wording or exact archiver contract prose.

#### Scenario: Prompt prose is edited without breaking renderer tests
GIVEN a valid prompt wording edit that preserves resource packaging and render structure
WHEN renderer tests run
THEN tests that replaced the deleted coverage do not fail because of exact wording, command prose, or result-envelope prose changes.

#### Scenario: Exact resource parity is not reintroduced
GIVEN a future valid change-agent addition discovered by production discovery
WHEN renderer resource tests run
THEN they do not fail because metadata and markdown resource sets are asserted as one exact frozen list.
