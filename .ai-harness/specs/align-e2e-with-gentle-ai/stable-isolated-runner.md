# Spec — stable isolated runner

## Purpose

Maintainers and CI can run the entire e2e suite through one documented
command, `./e2e/docker-test.sh`, isolated from the host filesystem and tool
environment. The runner is the only e2e entry point; everything else
(Docker build context, image choice, container cleanup, env forwarding)
sits behind it.

Public seam exercised: `e2e/docker-test.sh`.

## Requirements

### Requirement: single-canonical-entry-point

The system MUST advertise `./e2e/docker-test.sh` (invoked from the repo root)
as the only e2e command for local and CI use.

#### Scenario: command succeeds and exits cleanly

GIVEN Docker is installed, the repo root contains `e2e/docker-test.sh`, and
`e2e/Dockerfile` builds successfully
WHEN a maintainer runs `./e2e/docker-test.sh`
THEN the script builds the test image, runs `e2e/e2e_test.sh` inside the
container, prints the suite summary to stdout, and exits with the same code
as the container process

#### Scenario: no parallel entry points advertised

GIVEN the runner exists
WHEN a maintainer inspects `README.md`, `CONTEXT.md`, and `CODING_STANDARDS.md`
THEN every e2e run instruction references `./e2e/docker-test.sh` and no other
e2e entry point is documented as canonical

### Requirement: exit-code-passthrough

`e2e/docker-test.sh` MUST exit with the same code as the container's
`e2e_test.sh` process so CI gates stay simple.

#### Scenario: failure propagation

GIVEN a tier-1 test in `e2e_test.sh` is forced to fail (e.g. by introducing a
broken assertion)
WHEN a maintainer runs `./e2e/docker-test.sh`
THEN the runner exits non-zero and the script's exit code equals the failing
container's exit code

#### Scenario: success propagation

GIVEN all enabled tier tests pass
WHEN a maintainer runs `./e2e/docker-test.sh`
THEN the runner exits `0`

### Requirement: host-isolation

The runner MUST execute the suite in a container such that filesystem writes,
sandboxed `uv tool install`, and other side effects do not mutate the host's
home directory or tool store.

#### Scenario: home dir not mutated on success

GIVEN a clean host `~/.local` and `~/.cache`
WHEN a maintainer runs `./e2e/docker-test.sh` with `RUN_FULL_E2E=1` enabled
THEN after the run completes the host's `~/.local` and `~/.cache` are unchanged

#### Scenario: home dir not mutated on failure

GIVEN a clean host `~/.local` and `~/.cache`
WHEN a maintainer runs `./e2e/docker-test.sh` and a tier-2 test fails mid-run
THEN the host's `~/.local` and `~/.cache` are unchanged (writes stay inside the
container even on failure)

### Requirement: optional-platform-slot

The runner MUST accept at most one optional positional argument as a reserved
platform slot for a future distro matrix, but MUST NOT require it for v1.

#### Scenario: no-arg default

GIVEN Docker is installed
WHEN a maintainer runs `./e2e/docker-test.sh` with no arguments
THEN the runner proceeds with the v1 single-image flow

#### Scenario: future-platform-slot accepted

GIVEN the v1 runner is in place
WHEN a maintainer runs `./e2e/docker-test.sh ubuntu`
THEN the script accepts the argument without error (it MAY ignore it for v1)
and still produces a valid run

### Requirement: timeout-wrapping

The runner SHOULD wrap the container invocation in a timeout so a hung test
does not block CI indefinitely.

#### Scenario: hung test terminates

GIVEN a test inside `e2e_test.sh` hangs in an infinite loop
WHEN a maintainer runs `./e2e/docker-test.sh` with the documented timeout
THEN the runner terminates the container after the timeout and exits non-zero
with a timeout message on stderr