#!/usr/bin/env bash
# assert_container_required.test.sh — verifies the host-mutation guard
# inline in tests-prompts/run.sh.
#
# Strategy:
#   - Extract the function definition from run.sh via awk (robust pattern,
#     not regex on body).
#   - Run the function in a clean subshell with controlled env vars.
#   - The function honors env-var overrides for the marker file paths and
#     the cgroup path (CONTAINER_RUN_MARKER, CONTAINER_DOCKER_MARKER,
#     CONTAINER_CGROUP_PATH). Defaults match the Linux container
#     conventions. Tests use the overrides to point at temp files so no
#     root access is required.
#
# Scenarios (matches the spec subtasks for isolate-host-config-from-test-runs):
#   3.1 host-side invocation exits 2 with [FATAL]
#   3.2 container markers pass the guard silently
#   3.3 CONTAINER_REQUIRED_OK=1 escape hatch
#   3.4 env-var escape hatch is checked before container markers
#   3.5 marker checks fall through in order
#
# Exit codes: 0 on success, 1 on any sub-scenario failure.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SH="$SCRIPT_DIR/../run.sh"

if [ ! -f "$RUN_SH" ]; then
    printf '[FAIL] run.sh not found at %s\n' "$RUN_SH" >&2
    exit 1
fi

# Extract the assert_container_required() { ... } block from run.sh.
# Prints the opening line, every body line, the closing brace, then exits.
fn_def="$(awk '
    /^assert_container_required\(\) \{$/ { capture = 1; print; next }
    capture { print; if ($0 == "}") exit }
' "$RUN_SH")"

if [ -z "$fn_def" ] || ! printf '%s\n' "$fn_def" | grep -q '^assert_container_required() {$'; then
    printf '[FAIL] could not locate assert_container_required() in %s\n' "$RUN_SH" >&2
    printf 'first 5 lines of run.sh:\n' >&2
    head -n 5 "$RUN_SH" >&2
    exit 1
fi

FAIL=0

# Run `body` (a snippet of bash) in a clean subshell with the function
# pre-loaded. Returns the subshell's exit code; output is /dev/null'd.
run_body() {
    local body="$1"
    bash -c "${fn_def}; ${body}" >/dev/null 2>&1
}

# Like run_body, but returns stderr for inspection.
run_body_stderr() {
    local body="$1"
    bash -c "${fn_def}; ${body}" 2>&1 >/dev/null
}

assert_exit_eq() {
    local label="$1" expected="$2" body="$3"
    local actual
    run_body "$body"
    actual=$?
    if [ "$actual" -ne "$expected" ]; then
        printf '  [FAIL] %s: expected exit=%s, got exit=%s\n' \
            "$label" "$expected" "$actual" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_stderr_contains() {
    local label="$1" needle="$2" body="$3"
    local stderr_actual
    stderr_actual=$(run_body_stderr "$body")
    if [[ "$stderr_actual" != *"$needle"* ]]; then
        printf '  [FAIL] %s: stderr missing %q\n  got: %q\n' \
            "$label" "$needle" "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
}

assert_stderr_absent() {
    local label="$1" needle="$2" body="$3"
    local stderr_actual
    stderr_actual=$(run_body_stderr "$body")
    if [[ "$stderr_actual" == *"$needle"* ]]; then
        printf '  [FAIL] %s: stderr contained %q (must be silent)\n  got: %q\n' \
            "$label" "$needle" "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
}

# ---------------------------------------------------------------------------
# Scenario 3.1 — host-side invocation (no markers, no env) exits 2 + [FATAL].
# ---------------------------------------------------------------------------
assert_exit_eq "3.1a host invocation exits 2" 2 \
    'unset CONTAINER_REQUIRED_OK CONTAINER_RUN_MARKER CONTAINER_DOCKER_MARKER CONTAINER_CGROUP_PATH; assert_container_required'

assert_stderr_contains "3.1b host invocation stderr contains [FATAL]" \
    '[FATAL] refusing to run on the host: tests-prompts must be invoked via docker-test.sh' \
    'unset CONTAINER_REQUIRED_OK CONTAINER_RUN_MARKER CONTAINER_DOCKER_MARKER CONTAINER_CGROUP_PATH; assert_container_required'

# ---------------------------------------------------------------------------
# Scenario 3.3 — CONTAINER_REQUIRED_OK=1 escape hatch.
# ---------------------------------------------------------------------------
assert_exit_eq "3.3 CONTAINER_REQUIRED_OK=1 passes the guard" 0 \
    'CONTAINER_REQUIRED_OK=1 assert_container_required'

assert_stderr_absent "3.3b CONTAINER_REQUIRED_OK=1 is silent (no [FATAL])" \
    '[FATAL]' \
    'CONTAINER_REQUIRED_OK=1 assert_container_required'

# ---------------------------------------------------------------------------
# Scenario 3.4 — env-var escape hatch is checked FIRST.
# CONTAINER_REQUIRED_OK=1 with NO markers → guard passes.
# ---------------------------------------------------------------------------
assert_exit_eq "3.4 env-var escape precedes marker checks" 0 \
    'unset CONTAINER_RUN_MARKER CONTAINER_DOCKER_MARKER CONTAINER_CGROUP_PATH; CONTAINER_REQUIRED_OK=1 assert_container_required'

# ---------------------------------------------------------------------------
# Scenario 3.2 — container markers pass the guard.
# Use env-var overrides to point the marker checks at temp files.
# ---------------------------------------------------------------------------
marker_dir="$(mktemp -d "${TMPDIR:-/tmp}/ai-harness-guard-XXXXXX")"
trap 'rm -rf "$marker_dir"' EXIT

# 3.2a: /run/.containerenv equivalent (Podman/CRI-O marker).
touch "$marker_dir/run.containerenv"
assert_exit_eq "3.2a CONTAINER_RUN_MARKER passes the guard" 0 \
    "CONTAINER_RUN_MARKER='$marker_dir/run.containerenv' assert_container_required"

# 3.2b: /.dockerenv equivalent (Docker marker).
touch "$marker_dir/docker.env"
assert_exit_eq "3.2b CONTAINER_DOCKER_MARKER passes the guard" 0 \
    "CONTAINER_DOCKER_MARKER='$marker_dir/docker.env' assert_container_required"

# 3.2c: /proc/1/cgroup contains 'docker' → passes.
cat > "$marker_dir/cgroup.docker" <<'EOF'
1:net_cls:/
0::/docker/abc123
EOF
assert_exit_eq "3.2c cgroup contains 'docker' passes the guard" 0 \
    "CONTAINER_CGROUP_PATH='$marker_dir/cgroup.docker' assert_container_required"

# 3.2d: /proc/1/cgroup contains 'containerd' → passes.
cat > "$marker_dir/cgroup.containerd" <<'EOF'
13:devices::/system.slice/containerd.service
EOF
assert_exit_eq "3.2d cgroup contains 'containerd' passes the guard" 0 \
    "CONTAINER_CGROUP_PATH='$marker_dir/cgroup.containerd' assert_container_required"

# ---------------------------------------------------------------------------
# Scenario 3.5 — marker checks fall through in order. When none of the
# signals is present, the guard exits 2.
# ---------------------------------------------------------------------------
# Sanity: a cgroup file that does NOT contain docker|containerd must NOT
# cause the guard to pass. Proves the fall-through behavior.
cat > "$marker_dir/cgroup.bad" <<'EOF'
1:net_cls:/
0::/init.scope
EOF
assert_exit_eq "3.5 marker checks fall through (cgroup without docker/containerd)" 2 \
    "CONTAINER_CGROUP_PATH='$marker_dir/cgroup.bad' assert_container_required"

if [ "$FAIL" -gt 0 ]; then
    printf '\n[FAIL] %d sub-scenario(s) failed\n' "$FAIL" >&2
    exit 1
fi

printf '[OK] all assert_container_required sub-scenarios passed\n'
exit 0
