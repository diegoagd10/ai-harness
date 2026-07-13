# Spec — Deterministic configuration failure

## Purpose

Fail routed continuation atomically when repository configuration cannot safely supply context.

## Requirements

### Requirement: Validate configuration before routed context delivery
The system MUST require `ChangeConfigAdministrator.validate_config().is_valid` before calling `get_context_by` for an actionable continuation; validation warnings alone MUST NOT halt delivery.

#### Scenario: Continue with a non-halting warning
GIVEN configuration is valid but reports an unknown phase-key warning and the routed phase is configured
WHEN `ai-harness change-continue <change>` is invoked
THEN it succeeds and returns context for the routed phase.

#### Scenario: Reject schema-invalid configuration
GIVEN an actionable continuation and configuration validation returns `is_valid: false`
WHEN `ai-harness change-continue <change>` is invoked
THEN it fails through the established `ChangeStoreError` path without calling for or returning usable context.

### Requirement: Fail atomically for unavailable or unreadable configuration
The system MUST translate missing configuration, unreadable configuration, malformed YAML, schema-invalid configuration, and failures during the required context read into the established non-zero CLI error behavior.

#### Scenario: Fail for absent configuration
GIVEN an actionable continuation and no repository `.ai-harness/config.yml`
WHEN `ai-harness change-continue <change>` is invoked
THEN the command exits non-zero, writes a useful human-readable configuration error to stderr, and writes no status JSON to stdout.

#### Scenario: Fail for malformed YAML
GIVEN an actionable continuation and `.ai-harness/config.yml` contains malformed YAML
WHEN `ai-harness change-continue <change>` is invoked
THEN the command exits non-zero through the same error boundary and emits no partial status JSON.

#### Scenario: Fail for a read error after validation
GIVEN configuration validates successfully but the required `get_context_by` read fails
WHEN `ai-harness change-continue <change>` is invoked
THEN the failure is normalized to `ChangeStoreError`, the CLI exits non-zero, and no previously derived status is emitted.

### Requirement: Maintain response compatibility explicitly
The system MUST make the additive response shape detectable with schema version 2 rather than silently changing a version-1 response.

#### Scenario: Consume a version-2 change-new response
GIVEN a successful `change-new` command
WHEN its status JSON is consumed
THEN it contains all established status fields, `schemaVersion: 2`, and `configContext: null`.
