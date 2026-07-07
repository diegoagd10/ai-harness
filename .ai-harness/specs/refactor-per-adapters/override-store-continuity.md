# Spec — Override-store continuity

## Purpose

Prove the shared override-store helper preserves existing `~/.ai-harness/overrides.json` behavior for administrators and the wizard while maintaining the critical `overrides=None` versus `overrides={}` distinction.

## Requirements

### Requirement: Shared helper loads and saves override store
The system MUST provide `load_override_store(home)`, `save_override_store(home, payload)`, and `deep_merge(base, override)` through the shared override-store helper described by the design.

#### Scenario: Save deep-merges and preserves unrelated keys
GIVEN `home/.ai-harness/overrides.json` contains existing agent overrides and unrelated keys
WHEN `save_override_store(home, payload)` is called with a new model override
THEN the file is written as pretty, stable JSON with the payload deep-merged over existing data and unrelated keys preserved.

#### Scenario: Deep merge does not mutate inputs
GIVEN base and override dictionaries containing nested dicts, lists, scalars, and nulls
WHEN `deep_merge(base, override)` is called
THEN nested dictionaries merge recursively, lists/scalars/nulls replace, and neither input dictionary is mutated.

### Requirement: Override loading preserves existing failure semantics
The system MUST return `{}` when the override file is absent and MUST propagate `json.JSONDecodeError` for malformed override-store JSON.

#### Scenario: Missing override store is empty
GIVEN no `home/.ai-harness/overrides.json` file exists
WHEN `load_override_store(home)` is called
THEN it returns `{}`.

#### Scenario: Malformed override store propagates JSONDecodeError
GIVEN `home/.ai-harness/overrides.json` contains malformed JSON
WHEN `load_override_store(home)` is called
THEN `json.JSONDecodeError` propagates to the caller.

### Requirement: Administrators distinguish ambient and explicit overrides
Administrators MUST read `home/.ai-harness/overrides.json` only when `overrides is None`; administrators MUST NOT read disk when `overrides={}` is supplied.

#### Scenario: None reads disk but empty dict bypasses disk
GIVEN `home/.ai-harness/overrides.json` contains a model override for `change-explorer`
WHEN an administrator renders with `overrides=None`
THEN the rendered artifact reflects the disk override; GIVEN the same home, WHEN it renders with `overrides={}`, THEN the disk override is not read or applied.
