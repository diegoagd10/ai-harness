# Spec — isolate-host-config-from-test-runs

## Purpose

Running `tests-prompts` or `e2e` from the host (without going through `docker-test.sh`) calls `ai-harness install -o opencode` and `e2e/lib.sh::cleanup_test_env`, both of which mutate `$HOME/.ai-harness` and adjacent paths. The user reports losing their local config and having to re-run `ai-harness` afterward. Per-path backup/restore was rejected as a shallower alternative — it walks the shape of the bug instead of closing the bug class. The deeper cut: refuse to run on the host entirely, so no host path can be mutated regardless of which one the runner would have touched. The Dockerfiles already isolate `$HOME` inside the container (no `HOME` mount), so the bug only triggers when runner scripts are invoked directly on the host.

This slice adds `assert_container_required` inline in `tests-prompts/run.sh` AND in `e2e/lib.sh` (two copies — the duplication is intentional because `tests-prompts/run.sh` does not depend on `e2e/lib.sh`, and a shared lib for one function is worse than two 12-line copies). The guard refuses host-side runs unless a container signal is present or `CONTAINER_REQUIRED_OK=1` is set. A host-side smoke test backs up `~/.ai-harness`, runs the suite via `docker-test.sh`, and asserts byte-identical restoration — that's the verification of the user's symptom.

## Requirements

### Requirement: assert_container_required is defined in tests-prompts/run.sh

The system MUST define `assert_container_required` as a bash function inside `tests-prompts/run.sh`. It MUST be called near the top of `run.sh` (before any code path that mutates `~/.ai-harness`, `$HOME/.config/opencode`, etc.). On host detection, the function MUST write a labeled `[FATAL]` line to stderr naming the runner and the correct entrypoint, and MUST exit 2.

#### Scenario: host-side invocation exits 2

GIVEN `tests-prompts/run.sh` is invoked on a host where none of the container markers (`/run/.containerenv`, `/.dockerenv`, `/proc/1/cgroup` containing `docker`/`containerd`) exist and `CONTAINER_REQUIRED_OK` is unset
WHEN the script is run
THEN the script exits with code 2 and stderr contains `[FATAL] refusing to run on the host: tests-prompts must be invoked via docker-test.sh`

#### Scenario: container markers pass the guard

GIVEN `/run/.containerenv` exists (Podman/CRI-O) OR `/.dockerenv` exists (Docker) OR `/proc/1/cgroup` contains `docker`/`containerd`
WHEN `tests-prompts/run.sh` is invoked
THEN the guard passes silently and the script continues (no `[FATAL]`, no exit 2)

#### Scenario: CONTAINER_REQUIRED_OK=1 escape hatch

GIVEN `CONTAINER_REQUIRED_OK=1` is set in the environment
WHEN `tests-prompts/run.sh` is invoked on the host (no container markers)
THEN the guard passes silently (escape hatch for developers iterating on the runner itself)

### Requirement: assert_container_required is defined in e2e/lib.sh

The system MUST define `assert_container_required` as a bash function inside `e2e/lib.sh`, sourced by `e2e_test.sh`. It MUST be called shortly after the `set -uo pipefail` line in `lib.sh`, so every e2e script that sources `lib.sh` inherits the guard. The same container-marker detection rules and exit code 2 apply.

#### Scenario: e2e/lib.sh host-side sourcing exits 2

GIVEN `e2e/lib.sh` is sourced from a host shell where no container markers exist and `CONTAINER_REQUIRED_OK` is unset
WHEN the sourcing shell continues past the `source e2e/lib.sh` line
THEN the shell exits 2 with `[FATAL] refusing to run on the host: e2e must be invoked via e2e/docker-test.sh` on stderr

#### Scenario: e2e/docker-test.sh sets CONTAINER_REQUIRED_OK=1 in container

GIVEN `e2e/docker-test.sh` runs the container
WHEN the container starts
THEN the environment inside the container has `CONTAINER_REQUIRED_OK=1` (the Dockerfile or `docker run` command sets it), so `e2e/lib.sh::assert_container_required` passes inside the container even if the container markers are stripped

### Requirement: detection logic

The function MUST consider a run "containerized" if ANY of the following is true: (a) `$CONTAINER_REQUIRED_OK == "1"` (escape hatch, checked first), (b) `/run/.containerenv` exists, (c) `/.dockerenv` exists, (d) `/proc/1/cgroup` is readable and contains the substring `docker` or `containerd`. The checks MUST be ordered with the env-var escape hatch first.

#### Scenario: env-var escape hatch is checked first

GIVEN `CONTAINER_REQUIRED_OK=1` is set AND no container markers exist
WHEN the guard runs
THEN the guard passes (env var short-circuits the marker checks)

#### Scenario: marker checks fall through in order

GIVEN none of the four signals is present
WHEN the guard runs
THEN stderr names the absence of container markers (`/run/.containerenv`, `/.dockerenv`, `/proc/1/cgroup`) and exits 2

### Requirement: host-side smoke test verifies host config is untouched

The system MUST provide a host-side smoke test (script under `tests-prompts/tests/` or `e2e/tests/` per design placement) that: (1) snapshots `~/.ai-harness` (and adjacent paths) to a tempdir before the run; (2) invokes `./tests-prompts/docker-test.sh` (or `./e2e/docker-test.sh`) end-to-end; (3) asserts the snapshot is byte-identical after the run by re-tarring/md5-ing the same paths. The smoke test is a verification of the user's symptom, not an enforcement of the guard.

#### Scenario: smoke test passes after a clean docker-test.sh run

GIVEN the snapshot script records md5sums (or an equivalent content hash) of `~/.ai-harness`, `~/.config/opencode`, `~/.claude`, `~/.agents`, `~/.copilot`, `~/.github` before the run
WHEN `./tests-prompts/docker-test.sh` (or `./e2e/docker-test.sh`) completes
THEN the post-run md5sums match the pre-run md5sums byte-for-byte, and the smoke test exits 0

#### Scenario: smoke test catches a regression in the guard

GIVEN the guard in `assert_container_required` is removed (regression scenario)
WHEN a developer runs the smoke test
THEN the post-run md5sums of the host paths differ from the pre-run md5sums (the runner mutated `~/.ai-harness` because the guard was absent), and the smoke test exits non-zero

### Requirement: do not add per-path backup/restore

The system MUST NOT add snapshot/restore logic for individual config paths (e.g. `backup $HOME/.ai-harness to tmpdir; rm -rf $HOME/.ai-harness; ...; restore`). The container-required guard is the only isolation mechanism. This is the rejected alternative from `design.md`.

#### Scenario: no backup/restore helpers added

GIVEN the diff for this change
WHEN `grep -RnE 'snapshot.*HOME|backup.*\\.ai-harness|tar.*\\.ai-harness' tests-prompts/ e2e/` is run
THEN grep returns no matches (no per-path backup logic was added to close the bug class)

#### Scenario: cleanup_test_env rm-rf lines remain unreachable from host

GIVEN `assert_container_required` is in `e2e/lib.sh` AND exits 2 before `cleanup_test_env` is called
WHEN a developer tries to run `e2e_test.sh` directly on the host
THEN the script exits 2 at the guard, before any `rm -rf "$HOME/.ai-harness"` line executes (the user's symptom cannot be reproduced from a host run)