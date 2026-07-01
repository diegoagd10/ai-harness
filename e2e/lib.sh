#!/usr/bin/env bash
# lib.sh — shared test helpers for ai-harness E2E tests
set -euo pipefail

# ---------------------------------------------------------------------------
# assert_container_required — host-mutation guard.
#
# Closes Track B of fix-tests-prompts-assertions at its source for the
# e2e suite. Sourcing e2e/lib.sh on the host (without going through
# e2e/docker-test.sh) means the e2e entrypoint code below runs and may
# mutate $HOME/.ai-harness / $HOME/.config/opencode / etc. via
# `cleanup_test_env`. Refusing to source at all on a non-container host
# closes that bug class at its source.
#
# Two copies of this guard exist (this one and tests-prompts/run.sh).
# The duplication is intentional: e2e_test.sh and tests-prompts run.sh
# do not share a library; a shared lib for one function would be heavier
# than the 24 lines it would save.
#
# Container signals (passes if ANY is true, evaluated in order):
#   1. $CONTAINER_REQUIRED_OK == "1"             — escape hatch for host
#                                                  development of the
#                                                  e2e suite itself.
#   2. $CONTAINER_RUN_MARKER (default: /run/.containerenv) — Podman / CRI-O.
#   3. $CONTAINER_DOCKER_MARKER (default: /.dockerenv)   — Docker.
#   4. $CONTAINER_CGROUP_PATH   (default: /proc/1/cgroup) — cgroup fallback
#      must be readable AND contain 'docker' or 'containerd'.
#
# If none of those signals pass: write [FATAL] to stderr and exit 2.
#
# e2e/docker-test.sh forwards CONTAINER_REQUIRED_OK=1 into the container
# so the guard passes there even if container markers are stripped.
# CONTAINER_RUN_MARKER / CONTAINER_DOCKER_MARKER / CONTAINER_CGROUP_PATH
# redirect the marker checks for testing or for non-standard runtimes.
# ---------------------------------------------------------------------------
assert_container_required() {
    [ "${CONTAINER_REQUIRED_OK:-}" = "1" ] && return 0
    [ -f "${CONTAINER_RUN_MARKER:-/run/.containerenv}" ] && return 0
    [ -f "${CONTAINER_DOCKER_MARKER:-/.dockerenv}" ] && return 0
    local cgroup_path="${CONTAINER_CGROUP_PATH:-/proc/1/cgroup}"
    if [ -r "$cgroup_path" ]; then
        if grep -qE '(docker|containerd)' "$cgroup_path" 2>/dev/null; then
            return 0
        fi
    fi
    printf '[FATAL] refusing to run on the host: e2e must be invoked via e2e/docker-test.sh\n' >&2
    exit 2
}

# Guard the entire e2e suite at source-time. After this line, no e2e
# entrypoint code path is reachable on a non-container host.
assert_container_required

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# Counters
PASSED=0; FAILED=0; SKIPPED=0
TIER1_PASSED=0; TIER1_FAILED=0; TIER1_SKIPPED=0
TIER2_PASSED=0; TIER2_FAILED=0; TIER2_SKIPPED=0
TIER3_PASSED=0; TIER3_FAILED=0; TIER3_SKIPPED=0
CURRENT_TIER="${CURRENT_TIER:-}"

# Logging
log_test()  { printf "${YELLOW}[TEST]${NC}  %s\n" "$1"; }
log_pass()  { printf "${GREEN}[PASS]${NC}  %s\n" "${1:-ok}"; PASSED=$((PASSED+1)); case "$CURRENT_TIER" in tier1) TIER1_PASSED=$((TIER1_PASSED+1));; tier2) TIER2_PASSED=$((TIER2_PASSED+1));; tier3) TIER3_PASSED=$((TIER3_PASSED+1));; esac; }
log_fail()  { printf "${RED}[FAIL]${NC}  %s\n" "${1:-FAIL}"; FAILED=$((FAILED+1)); case "$CURRENT_TIER" in tier1) TIER1_FAILED=$((TIER1_FAILED+1));; tier2) TIER2_FAILED=$((TIER2_FAILED+1));; tier3) TIER3_FAILED=$((TIER3_FAILED+1));; esac; }
log_skip()  { printf "${BLUE}[SKIP]${NC}  %s\n" "$1"; SKIPPED=$((SKIPPED+1)); case "$CURRENT_TIER" in tier1) TIER1_SKIPPED=$((TIER1_SKIPPED+1));; tier2) TIER2_SKIPPED=$((TIER2_SKIPPED+1));; tier3) TIER3_SKIPPED=$((TIER3_SKIPPED+1));; esac; }
log_info()  { printf "${BLUE}[INFO]${NC}  %s\n" "$1"; }

# Resolve ai-harness binary (priority: AI_HARNESS_BINARY env > PATH)
resolve_binary() {
    [ -n "${AI_HARNESS_BINARY:-}" ] && [ -x "$AI_HARNESS_BINARY" ] && { echo "$AI_HARNESS_BINARY"; return 0; }
    command -v ai-harness >/dev/null 2>&1 && { echo "ai-harness"; return 0; }
    return 1
}

# Reset filesystem state between tests
cleanup_test_env() {
    rm -rf "$HOME/.config/opencode" "$HOME/.claude" "$HOME/.agents" "$HOME/.copilot" "$HOME/.github" "$HOME/.ai-harness" 2>/dev/null || true
    mkdir -p "$HOME/.config"
}

# Assertions
assert_file_exists() { [ -f "$1" ] && log_pass "File exists: ${2:-$1}" || { log_fail "File NOT found: ${2:-$1}"; return 1; }; }
assert_file_not_exists() { [ ! -f "$1" ] && log_pass "File absent: ${2:-$1}" || { log_fail "File should NOT exist: ${2:-$1}"; return 1; }; }
assert_dir_exists()   { [ -d "$1" ] && log_pass "Dir exists: ${2:-$1}" || { log_fail "Dir NOT found: ${2:-$1}"; return 1; }; }

assert_file_contains() {
    [ ! -f "$1" ] && { log_fail "File not found: $1"; return 1; }
    grep -q "$2" "$1" && log_pass "$3" || { log_fail "Pattern NOT found: '$2' in $1"; return 1; }
}

assert_file_size_min() {
    [ ! -f "$1" ] && { log_fail "File not found: $1"; return 1; }
    local sz; sz=$(wc -c < "$1" | tr -d ' ')
    [ "$sz" -ge "$2" ] && log_pass "${3:-File size} (${sz}b)" || { log_fail "File too small: $1 is ${sz}b, expected >= ${2}b"; return 1; }
}

assert_valid_json() {
    [ ! -f "$1" ] && { log_fail "File not found: $1"; return 1; }
    python3 -c "import json; json.load(open('$1'))" 2>/dev/null && log_pass "${2:-$1 is valid JSON}" || { log_fail "Invalid JSON: $1"; return 1; }
}

assert_output_contains() {
    echo "$1" | grep -qi "$2" && log_pass "${3:-output contains '$2'}" || { log_fail "Output does NOT contain '$2'"; return 1; }
}

assert_md5_match() {
    [ ! -f "$1" ] && { log_fail "File not found: $1"; return 1; }
    [ ! -f "$2" ] && { log_fail "File not found: $2"; return 1; }
    local h1 h2; h1=$(md5sum "$1" | cut -d' ' -f1); h2=$(md5sum "$2" | cut -d' ' -f1)
    [ "$h1" = "$h2" ] && log_pass "${3:-md5 match}" || { log_fail "md5 mismatch: $1 ($h1) != $2 ($h2)"; return 1; }
}

print_summary() {
    echo ""
    echo "========================================"
    echo "  E2E Test Summary"
    echo "========================================"
    printf "  Tier 1  ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" "$TIER1_PASSED" "$TIER1_FAILED" "$TIER1_SKIPPED"
    printf "  Tier 2  ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" "$TIER2_PASSED" "$TIER2_FAILED" "$TIER2_SKIPPED"
    printf "  Tier 3  ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" "$TIER3_PASSED" "$TIER3_FAILED" "$TIER3_SKIPPED"
    echo "  ========================================"
    printf "  OVERALL ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" "$PASSED" "$FAILED" "$SKIPPED"
    printf "  TOTAL  : %d\n" "$((PASSED + FAILED + SKIPPED))"
    echo "========================================"
    [ "$FAILED" -gt 0 ] && { printf "\n%bSome tests failed.%b\n" "$RED" "$NC"; return 1; }
    printf "\n%bAll tests passed.%b\n" "$GREEN" "$NC"
    return 0
}
