# Spec — Must-fix renderer isolation

## Purpose

Ensure renderer and metadata unit tests that are not testing the override store never read the developer's real `HOME`.

## Requirements

### Requirement: Direct renderer calls use explicit isolation
The system MUST update each must-fix direct `render_artifacts()` call in `tests/test_renderers.py` to run with `home=tmp_path` and `overrides={}` unless the test is explicitly categorized as override-store disk coverage.

#### Scenario: Non-store renderer test is isolated
GIVEN a test from the must-fix direct-call list renders artifacts for Claude, OpenCode, Copilot, or native agent CLIs
WHEN the test calls `render_artifacts()`
THEN the call uses `home=tmp_path` and `overrides={}`.

#### Scenario: Non-store renderer test cannot read real home
GIVEN the developer has a real `~/.ai-harness/overrides.json`
WHEN a must-fix non-store renderer test runs
THEN the test result is unaffected by that file because the renderer receives explicit in-memory empty overrides.

### Requirement: Direct metadata calls use explicit isolation
The system MUST update each must-fix direct `get_agent_metadata()` call that is not testing disk auto-load behavior to run with `home=tmp_path` and `overrides={}`.

#### Scenario: Metadata assertion is isolated
GIVEN a frontmatter or metadata test asserts template-derived fields
WHEN the test calls `get_agent_metadata()`
THEN the call includes `home=tmp_path` and `overrides={}`.

#### Scenario: Local metadata overrides are ignored
GIVEN the real user override store contains metadata for the same agent
WHEN the metadata test runs
THEN the asserted metadata comes from the template and test-provided arguments only.

### Requirement: Multi-call tests isolate every relevant call
The system MUST update every in-scope renderer or metadata call within an affected test, not only the first occurrence.

#### Scenario: Native CLI loop is isolated for every CLI
GIVEN a test renders the same capability across multiple native CLIs
WHEN the loop invokes renderer APIs for each CLI
THEN every invocation passes `home=tmp_path` and `overrides={}`.

#### Scenario: Partial migration is rejected
GIVEN an affected test has multiple `render_artifacts()` or `get_agent_metadata()` calls
WHEN one call still omits `home` or `overrides`
THEN the implementation does not satisfy this spec.
