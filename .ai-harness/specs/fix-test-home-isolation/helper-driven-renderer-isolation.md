# Spec — Helper-driven renderer isolation

## Purpose

Prevent shared test helpers from hiding transitive renderer reads of the real user `HOME`.

## Requirements

### Requirement: Shared helpers accept an isolated home
The system MUST change `_change_orchestrator_body`, `_native_change_orchestrator_body`, and `_native_change_implementor_body` to accept an isolated `home: Path` argument.

#### Scenario: Helper receives tmp_path from caller
GIVEN a body-contract test calls one of the shared helper functions
WHEN the helper is invoked
THEN the caller passes `home=tmp_path` or an equivalent explicit isolated path argument.

#### Scenario: Helper without home is invalid
GIVEN a shared helper invocation omits the isolated home argument
WHEN the test suite is audited or executed
THEN the helper call is considered non-compliant because it can no longer prove renderer isolation.

### Requirement: Helpers forward isolation to renderers
The system MUST make each helper forward `home=home` and `overrides={}` to its internal renderer or administrator render call.

#### Scenario: Orchestrator body helper forwards isolation
GIVEN `_change_orchestrator_body` renders the change orchestrator artifact
WHEN it calls `render_artifacts()`
THEN it passes `home=home` and `overrides={}`.

#### Scenario: Native body helpers forward isolation
GIVEN `_native_change_orchestrator_body` or `_native_change_implementor_body` renders through `ADMINISTRATORS[cli]`
WHEN the administrator render method is called
THEN it receives `home=home` and `overrides={}`.

### Requirement: All helper callers preserve parametrization
The system SHOULD update helper-backed tests mechanically without changing their existing CLI parametrization or assertion intent.

#### Scenario: Parametrized native helper test remains parametrized
GIVEN a native body test is parametrized by `cli`
WHEN `tmp_path: Path` is added to its signature
THEN the existing `cli` parameter remains active and the helper receives both `cli` and `home=tmp_path`.

#### Scenario: Assertion behavior is not rewritten
GIVEN a helper-backed test checks prompt body content
WHEN the helper call is migrated for isolation
THEN the prompt assertion remains focused on the same content and no Child C prompt rewrite is introduced.
