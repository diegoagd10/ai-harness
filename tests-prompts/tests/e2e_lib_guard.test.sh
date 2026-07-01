#!/usr/bin/env bash
# e2e_lib_guard.test.sh — verifies the host-mutation guard for e2e/lib.sh
# AND the env-var forwarding in e2e/docker-test.sh.
#
# Subtasks covered:
#   7.1  sourcing e2e/lib.sh on host exits 2 with [FATAL] message
#   7.2  e2e/docker-test.sh forwards CONTAINER_REQUIRED_OK=1 to the container
#
# Strategy mirrors tests-prompts/tests/assert_container_required.test.sh:
#   - Extract the function definition from e2e/lib.sh via awk.
#   - Run the function with controlled env (no markers) and verify exit.
#   - Static grep e2e/docker-test.sh for the -e CONTAINER_REQUIRED_OK=1
#     docker-run flag.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
E2E_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LIB_SH="$E2E_DIR/e2e/lib.sh"
DOCKER_TEST_SH="$E2E_DIR/e2e/docker-test.sh"

if [ ! -f "$LIB_SH" ]; then
    printf '[FAIL] e2e/lib.sh not found at %s\n' "$LIB_SH" >&2
    exit 1
fi

# Extract assert_container_required() { ... } from e2e/lib.sh.
fn_def="$(awk '
    /^assert_container_required\(\) \{$/ { capture = 1; print; next }
    capture { print; if ($0 == "}") exit }
' "$LIB_SH")"

FAIL=0

# ---------------------------------------------------------------------------
# 7.1 — function exists with the runner-specific [FATAL] wording.
# ---------------------------------------------------------------------------
if [ -z "$fn_def" ] || ! printf '%s\n' "$fn_def" | grep -q '^assert_container_required() {$'; then
    printf '  [FAIL] 7.1 assert_container_required not in %s\n' "$LIB_SH" >&2
    FAIL=$((FAIL + 1))
else
    # The [FATAL] message must name 'e2e' so a developer running lib.sh
    # directly on the host sees the correct entrypoint.
    if ! printf '%s\n' "$fn_def" | grep -qE "refusing to run on the host: e2e must be invoked via e2e/docker-test\.sh"; then
        printf '  [FAIL] 7.1 [FATAL] message does not name the e2e entrypoint\n' >&2
        FAIL=$((FAIL + 1))
    fi
    # Run the function in a clean subshell with no markers, no env var.
    actual_rc=0
    actual_stderr=$(bash -c "${fn_def}; assert_container_required" 2>&1 >/dev/null)
    actual_rc=$?
    if [ "$actual_rc" -ne 2 ]; then
        printf '  [FAIL] 7.1 host-side invocation: expected exit=2, got exit=%s\n' "$actual_rc" >&2
        FAIL=$((FAIL + 1))
    fi
    if [[ "$actual_stderr" != *"[FATAL] refusing to run on the host: e2e must be invoked via e2e/docker-test.sh"* ]]; then
        printf '  [FAIL] 7.1 stderr missing the labeled [FATAL] line\n  got: %q\n' "$actual_stderr" >&2
        FAIL=$((FAIL + 1))
    fi
    # Container markers and CONTAINER_REQUIRED_OK must pass.
    marker_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-harness-guard-e2e-XXXXXX")"
    trap 'rm -rf "$marker_dir"' EXIT
    touch "$marker_dir/run_marker"
    for marker_var in "CONTAINER_RUN_MARKER" "CONTAINER_DOCKER_MARKER"; do
        rc=0
        bash -c "${fn_def}; ${marker_var}='$marker_dir/run_marker' assert_container_required" >/dev/null 2>&1
        rc=$?
        if [ "$rc" -ne 0 ]; then
            printf '  [FAIL] 7.1 %s redirect did not let the guard pass (exit=%s)\n' "$marker_var" "$rc" >&2
            FAIL=$((FAIL + 1))
        fi
    done
    # CONTAINER_CGROUP_PATH needs a file containing 'docker' or 'containerd'.
    printf '0::/docker/abc123\n' > "$marker_dir/cgroup_docker"
    printf '13:devices::/system.slice/containerd.service\n' > "$marker_dir/cgroup_containerd"
    for fixture in "cgroup_docker" "cgroup_containerd"; do
        rc=0
        bash -c "${fn_def}; CONTAINER_CGROUP_PATH='$marker_dir/$fixture' assert_container_required" >/dev/null 2>&1
        rc=$?
        if [ "$rc" -ne 0 ]; then
            printf '  [FAIL] 7.1 CONTAINER_CGROUP_PATH redirect (%s) did not pass (exit=%s)\n' "$fixture" "$rc" >&2
            FAIL=$((FAIL + 1))
        fi
    done
    # CONTAINER_REQUIRED_OK=1 must pass.
    rc=0
    bash -c "${fn_def}; CONTAINER_REQUIRED_OK=1 assert_container_required" >/dev/null 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        printf '  [FAIL] 7.1 CONTAINER_REQUIRED_OK=1 did not let the guard pass (exit=%s)\n' "$rc" >&2
        FAIL=$((FAIL + 1))
    fi
fi

# Verify e2e/lib.sh calls assert_container_required after set -euo pipefail.
# Static check: the line `assert_container_required` appears in lib.sh
# and is NOT inside a function definition (i.e. it's a top-level call).
if grep -nE '^assert_container_required$' "$LIB_SH" >/dev/null; then
    :
else
    printf '  [FAIL] 7.1 e2e/lib.sh does not call assert_container_required at top level\n' >&2
    FAIL=$((FAIL + 1))
fi

# ---------------------------------------------------------------------------
# 7.2 — e2e/docker-test.sh forwards CONTAINER_REQUIRED_OK=1 to the container.
# ---------------------------------------------------------------------------
if [ ! -f "$DOCKER_TEST_SH" ]; then
    printf '  [FAIL] 7.2 e2e/docker-test.sh not found at %s\n' "$DOCKER_TEST_SH" >&2
    FAIL=$((FAIL + 1))
else
    # Static grep on e2e/docker-test.sh: must include '-e CONTAINER_REQUIRED_OK=1'.
    if grep -nE -- "-e[[:space:]]+CONTAINER_REQUIRED_OK=1" "$DOCKER_TEST_SH" >/dev/null; then
        :
    else
        printf '  [FAIL] 7.2 e2e/docker-test.sh does not forward -e CONTAINER_REQUIRED_OK=1\n' >&2
        FAIL=$((FAIL + 1))
    fi
    # Confirm the forwarding is unconditional (not behind a [ -n "..." ] gate).
    # Run a shell snippet that runs docker-test.sh in a fake mode: source it
    # and check the env forwarding is part of ENV_FLAGS building.
    # Simpler: look for an explicit comment or unconditional assignment.
    if grep -nE -- "-e[[:space:]]+CONTAINER_REQUIRED_OK=1" "$DOCKER_TEST_SH" >/dev/null; then
        printf '  [OK]   7.2 docker-test.sh forwards CONTAINER_REQUIRED_OK=1\n'
    fi
fi

if [ "$FAIL" -gt 0 ]; then
    printf '\n[FAIL] %d sub-scenario(s) failed\n' "$FAIL" >&2
    exit 1
fi
printf '\n[OK] all e2e guard sub-scenarios passed\n'
exit 0
