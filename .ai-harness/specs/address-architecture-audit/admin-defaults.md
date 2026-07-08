# Spec — Administrator default metadata and discovery

## Capability

Administrator default metadata and discovery — move shared metadata/discovery behavior to `ArtifactsAdministrator` while preserving the existing public administrator contract.

## Requirements

1. **R1: Base defaults.** `ArtifactsAdministrator` MUST provide concrete default implementations for `get_agent_metadata()` and `discover_agent_names()` with the same public signatures used before this change.
2. **R2: Provider-specific rendering.** `ArtifactsAdministrator.render_artifacts()` MUST remain abstract, and concrete administrator subclasses MUST continue to provide provider-specific rendering behavior.
3. **R3: Wrapper removal.** `ClaudeArtifactsAdministrator`, `CopilotArtifactsAdministrator`, and `OpenCodeArtifactsAdministrator` MUST NOT define `get_agent_metadata()` or `discover_agent_names()` methods after this change.
4. **R4: Public contract preservation.** Existing callers through `ADMINISTRATORS[...]` and polymorphic `ArtifactsAdministrator` references MUST continue to call `get_agent_metadata()` and `discover_agent_names()` without call-site changes.
5. **R5: Import cleanup.** Provider subclass modules SHOULD NOT import helper names that were only needed by the deleted wrappers, including `_resolve_agent_metadata`, `AgentMetadata`, or module-level `discover_agent_names()`.

## Scenarios

### Scenario: Claude administrator inherits default agent discovery

GIVEN a `ClaudeArtifactsAdministrator` instance after the change
WHEN `discover_agent_names()` is called on the instance
THEN it returns the same list as the module-level administrator discovery helper.

### Scenario: Copilot administrator inherits default metadata resolution

GIVEN `ADMINISTRATORS[AgentCli.COPILOT]` after the change
WHEN `get_agent_metadata("example")` is called
THEN it returns the same metadata as the previous Copilot wrapper returned for the same agent name.

### Scenario: OpenCode administrator preserves override-aware metadata resolution

GIVEN `ADMINISTRATORS[AgentCli.OPENCODE]` and metadata overrides after the change
WHEN `get_agent_metadata("example", overrides=overrides, home=home)` is called
THEN the returned metadata matches the prior `_resolve_agent_metadata()` behavior for the same arguments.

### Scenario: Subclasses no longer define discovery wrappers

GIVEN the three provider subclass files after the change
WHEN they are searched for `def discover_agent_names`
THEN zero matches are found in `claude.py`, `copilot.py`, and `opencode.py`.

### Scenario: Subclasses no longer define metadata wrappers

GIVEN the three provider subclass files after the change
WHEN they are searched for `def get_agent_metadata`
THEN zero matches are found in `claude.py`, `copilot.py`, and `opencode.py`.

### Scenario: Rendering remains abstract on the base class

GIVEN `ArtifactsAdministrator` after the change
WHEN its abstract methods are inspected
THEN `render_artifacts` is still abstract and `get_agent_metadata` and `discover_agent_names` are not abstract.

### Scenario: Provider rendering remains available through dispatch

GIVEN an existing administrator selected from `ADMINISTRATORS` after the change
WHEN `render_artifacts(...)` is invoked with valid provider inputs
THEN provider-specific artifact rendering still occurs through the concrete subclass.

### Scenario: Wrapper-only imports are removed from provider modules

GIVEN each provider subclass module after the change
WHEN its imports are inspected
THEN imports used only by the deleted metadata/discovery wrappers are absent.

## Out of scope

- Do not replace `ArtifactsAdministrator` with a `Protocol`, callable strategy, or administrator strategy redesign.
- Do not change runtime behavior, public method names, or call sites that already use `ADMINISTRATORS[...]`.
- Do not modify `e2e/`, `test-harness/`, `expected/`, README path references, `CODING_STANDARDS.md`, `AGENTS.md`, or `pyproject.toml` for this capability.
