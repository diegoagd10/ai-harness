#!/usr/bin/env bash
# lib.sh — shared test helpers for ai-harness E2E tests
set -euo pipefail

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
