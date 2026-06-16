# E2E Tests Specification

## Purpose

Defines the end-to-end test suite for the ai-harness CLI. Covers invocation, category isolation, two-lifecycle sandboxing, Docker integration, and coverage scope.

## Lifecycle Distinction (Critical)

The suite manages **two independent lifecycles**:

| Lifecycle | Command | Role | Isolation rule |
|-----------|---------|------|----------------|
| **A: CLI binary provisioning** | `uv tool install .`, `uv tool install --reinstall .`, `uv tool uninstall ai-harness` | Test infrastructure — makes `ai-harness` available on PATH | MUST be sandboxed (Docker container or isolated `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`). MUST NOT install ai-harness on the developer's real machine. |
| **B: Product harness** | `ai-harness install`, `ai-harness uninstall` | System under test — fans AGENTS.md, skills, prompts into HOME | MUST target synthetic HOME directories (`mktemp -d`). MUST NOT write to the developer's real HOME. |

## ADDED Requirements

### Requirement: Sandboxed CLI Binary Provisioning

The suite SHALL provision the `ai-harness` CLI binary via `uv tool install` into an isolated location. Local execution MUST NOT install or modify `ai-harness` in the developer's real uv tool registry or PATH.

#### Scenario: Docker execution isolates binary provisioning

- GIVEN e2e runs inside a Docker container built from `e2e/Dockerfile`
- WHEN `uv tool install` and `uv tool uninstall` execute inside the container
- THEN the binary is installed only within the container filesystem
- AND the host machine's uv tools and PATH are unchanged

#### Scenario: Local execution uses isolated uv tool directories

- GIVEN e2e runs locally (not in Docker)
- WHEN the suite provisions the CLI binary
- THEN `UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` are set to test-owned temporary directories
- AND `uv tool install` writes only to those directories
- AND `uv tool uninstall` removes the binary from those directories on completion

### Requirement: Synthetic HOME Isolation

Product behavior tests SHALL target synthetic HOME directories. No test SHALL write harness assets to the developer's real HOME.

#### Scenario: Product install targets synthetic HOME

- GIVEN any test invokes `ai-harness install`
- WHEN the command executes
- THEN the `HOME` environment variable points to a temporary directory (not the developer's real HOME)
- AND AGENTS.md, skills, and prompts are written inside that synthetic directory

#### Scenario: Synthetic directories cleaned up

- GIVEN any e2e task has completed (success or failure)
- WHEN the task tears down
- THEN all synthetic HOME directories are removed
- AND all isolated uv tool directories are removed

## MODIFIED Requirements

### Requirement: Invoke-Based Test Runner

The e2e suite SHALL run via Python Invoke from `e2e/tasks.py`. `uv run inv test` MUST execute all categories. `uv run inv <category>` SHALL run a single category in isolation.
(Previously: GIVEN conditions used ambiguous "ai-harness is installed" without sandboxing.)

#### Scenario: Run all categories

- GIVEN the CLI binary is provisioned in a sandbox (Docker container or isolated uv tool dirs)
- WHEN `uv run inv test` executes
- THEN install, uninstall, sdd_status, and sdd_continue tasks run
- AND exit code is 0 only if every category passes

#### Scenario: Run single category

- GIVEN the CLI binary is provisioned in a sandbox
- WHEN `uv run inv sdd_status` executes
- THEN only sdd_status tasks run
- AND exit code reflects that category's outcome independently

### Requirement: Category Task Separation

The e2e suite SHALL provide discrete Invoke tasks: `install`, `uninstall`, `sdd_status`, `sdd_continue`, and `tool_lifecycle`. Each task MUST be independently invokable and MUST NOT depend on execution order across tasks. Test bodies SHALL reside in lifecycle files organized by shared knowledge: `test_harness_lifecycle.py` (install and uninstall — shared file-layout invariants, backup/restore rules, user-file preservation), `test_sdd_lifecycle.py` (sdd-status and sdd-continue — shared `_run_sdd_resolve` / `resolve` logic and seeded-workspace knowledge), and `test_tool_lifecycle.py` (binary provisioning — no product knowledge). The `install` and `uninstall` Invoke tasks SHALL delegate to `test_harness_lifecycle.py`. The `sdd_status` and `sdd_continue` Invoke tasks SHALL delegate to `test_sdd_lifecycle.py`. The `tool_lifecycle` task covers Lifecycle A (binary provisioning, sandboxed). `install` and `uninstall` tasks cover Lifecycle B (product harness into synthetic HOME).
(Previously: required separate per-command test files; revised to lifecycle files by shared knowledge — install/uninstall share file invariants, sdd-status/continue share resolve logic.)

#### Scenario: Category test logic isolated in lifecycle files

- GIVEN any lifecycle domain (harness lifecycle, SDD lifecycle, tool lifecycle)
- WHEN a developer needs to read or modify that domain's test assertions
- THEN the assertions for that domain SHALL reside in a single lifecycle file dedicated to that domain
- AND lifecycle files SHALL NOT share domain-specific knowledge (file invariants, workspace structure, binary management) across file boundaries
- AND the Invoke task entry point (`e2e/tasks.py`) SHALL NOT contain test bodies
- AND shared infrastructure (`e2e/harness.py`) SHALL NOT contain lifecycle-specific assertions

#### Scenario: Install category runs independently

- GIVEN a sandboxed test environment and synthetic HOME directories
- WHEN `uv run inv install` executes
- THEN the CLI binary is provisioned via `uv tool install` in the sandbox
- AND product install assertions (fresh install, reinstall, idempotent override, backup/restore, file content) execute against synthetic HOME
- AND no uninstall, sdd_status, or sdd_continue tasks are triggered

#### Scenario: SDD categories do not depend on product install state

- GIVEN a seeded OpenSpec workspace (via synthetic seed, not prior `ai-harness install`)
- WHEN `uv run inv sdd_status` executes
- THEN sdd_status assertions pass without requiring the install task to have run first
- AND no product harness assets exist in the test environment

### Requirement: Install/Uninstall Assertion Parity

All assertions from the existing `e2e/e2e_test.sh` SHALL be preserved. Coverage MUST include: fresh install, reinstall, idempotent override, file existence, file content, backup/restore, and clean uninstall. All product assertions (Lifecycle B) SHALL target synthetic HOME directories. Binary provisioning assertions (Lifecycle A) SHALL execute within the sandbox.
(Previously: did not specify synthetic HOME or sandboxing for local execution.)

#### Scenario: Fresh install creates expected files

- GIVEN a synthetic HOME directory with no ai-harness artifacts
- WHEN the install task runs `ai-harness install` with HOME set to that directory
- THEN AGENTS.md, skills, and OpenCode prompts exist under the synthetic HOME
- AND content matches the bundled source
- AND the developer's real HOME is untouched

#### Scenario: Reinstall backs up user files

- GIVEN a synthetic HOME with a prior install and user-modified AGENTS.md
- WHEN the install task runs `ai-harness install` again with HOME set to that directory
- THEN the modified AGENTS.md is backed up before overwrite
- AND the backup is preserved under a timestamped path within the synthetic HOME

#### Scenario: Uninstall removes artifacts from synthetic HOME

- GIVEN ai-harness was installed into a synthetic HOME
- WHEN the uninstall task runs `ai-harness uninstall` with HOME set to that directory
- THEN installed files are removed from the synthetic HOME
- AND user files not owned by ai-harness remain untouched

### Requirement: Docker Test Harness Compatibility

Docker e2e execution SHALL use the Invoke entrypoint. The image MUST include `invoke`, and `CMD` MUST default to `uv run inv test`. The Docker container SHALL serve as a fully isolated sandbox: both Lifecycle A (binary provisioning) and Lifecycle B (product assertions) execute entirely inside the container with zero host-side effects.
(Previously: did not mandate zero host-side effects.)

#### Scenario: Docker runs via Invoke in full isolation

- GIVEN a built Docker image from `e2e/Dockerfile`
- WHEN the container starts
- THEN `inv test` executes all categories inside the container
- AND exit code reports pass/fail
- AND no binaries, files, or artifacts leak to the host machine
