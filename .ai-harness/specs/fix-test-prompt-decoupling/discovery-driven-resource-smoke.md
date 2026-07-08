# Spec — Discovery-driven resource smoke

## Purpose

Verify change-agent resource packaging through production discovery and metadata loading without freezing exact agent sets or prompt prose.

## Requirements

### Requirement: Use discovered agents as the source of truth
The system MUST add `test_change_agent_resources_smoke_have_metadata_and_body` driven by `discover_agent_names()`.

#### Scenario: Discovery returns a minimum viable catalog
GIVEN packaged change-agent resources
WHEN `test_change_agent_resources_smoke_have_metadata_and_body` calls `discover_agent_names()`
THEN it asserts `len(discover_agent_names()) >= 9`.

#### Scenario: Future valid agents are allowed
GIVEN a future change adds a valid discovered change-agent resource
WHEN the smoke test runs
THEN it does not fail because the discovered names differ from an exact frozen list.

### Requirement: Each discovered agent has a usable template and metadata
The system MUST verify every discovered agent has a same-name markdown template with a non-empty body and loadable metadata with a non-empty description.

#### Scenario: Complete resource passes smoke
GIVEN a discovered agent name with `change-agent/{name}.md` and valid metadata
WHEN the smoke test checks that name
THEN the markdown template exists, its text is non-empty after stripping whitespace, and `load_agent_metadata(name).description` is truthy.

#### Scenario: Missing template is caught
GIVEN discovery returns an agent name whose same-name markdown template is missing
WHEN the smoke test checks that name
THEN the test fails with a missing-template signal instead of silently accepting incomplete packaging.

#### Scenario: Empty template body is caught
GIVEN discovery returns an agent name whose markdown template contains only whitespace
WHEN the smoke test reads the template body
THEN the test fails because the stripped body is empty.
