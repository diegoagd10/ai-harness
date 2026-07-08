# Spec — Override-store disk isolation

## Purpose

Preserve override-store disk-read coverage while redirecting all disk access to pytest-controlled temporary homes.

## Requirements

### Requirement: Override-store tests use tmp_path as HOME seam
The system MUST ensure the 10 override-store-specific tests use `home=tmp_path` for renderer or metadata calls that intentionally exercise disk loading.

#### Scenario: Store-loading metadata test reads tmp_path store
GIVEN a metadata test writes an override store fixture under `tmp_path / OVERRIDES_REL`
WHEN it calls `get_agent_metadata()` for auto-loading behavior
THEN the call uses `home=tmp_path` and reads only that temporary store.

#### Scenario: Real home store is not consulted
GIVEN the real user home contains `.ai-harness/overrides.json`
WHEN an override-store-specific test runs
THEN the renderer or metadata API does not read that real file because `home=tmp_path` redirects the disk path.

### Requirement: Disk-read semantics are preserved
The system MUST keep `overrides=None` or omitted `overrides` where the test's purpose is default auto-load, missing-store behavior, malformed-store behavior, or omitted-vs-`None` equivalence.

#### Scenario: Auto-load coverage remains active
GIVEN a test verifies that override metadata is loaded from disk
WHEN it calls renderer or metadata APIs
THEN it does not replace the disk-read path with `overrides={}`.

#### Scenario: Equivalence tests keep None/default distinction
GIVEN a byte-identical no-overrides test compares omitted overrides with `overrides=None`
WHEN both render calls are migrated
THEN both calls use `home=tmp_path` while preserving the omitted/default and `None` override forms under comparison.

### Requirement: Missing and malformed store cases stay scoped
The system SHOULD preserve existing missing-store and malformed-store assertions while isolating their filesystem root.

#### Scenario: Missing store remains a noop
GIVEN no override store exists under `tmp_path / OVERRIDES_REL`
WHEN a missing-store test calls the API with disk semantics
THEN the result remains the default template metadata or artifacts.

#### Scenario: Malformed store raises from tmp_path fixture
GIVEN a malformed override store is written under `tmp_path / OVERRIDES_REL`
WHEN the malformed-store test calls the API with disk semantics
THEN the expected error is raised from the temporary fixture, not from real user state.
