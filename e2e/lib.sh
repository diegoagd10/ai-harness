#!/usr/bin/env bash
# lib.sh — shared test helpers for ai-harness E2E tests
# Sourced by e2e_test.sh; never executed directly.
set -euo pipefail

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------
PASSED=0
FAILED=0
SKIPPED=0

# Per-tier counters
TIER1_PASSED=0; TIER1_FAILED=0; TIER1_SKIPPED=0
TIER2_PASSED=0; TIER2_FAILED=0; TIER2_SKIPPED=0
TIER3_PASSED=0; TIER3_FAILED=0; TIER3_SKIPPED=0

# Current tier context (set by e2e_test.sh before running each tier)
CURRENT_TIER="${CURRENT_TIER:-}"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_test()  { printf "${YELLOW}[TEST]${NC}  %s\n" "$1"; }
log_pass()  {
    printf "${GREEN}[PASS]${NC}  %s\n" "$1"
    PASSED=$((PASSED + 1))
    case "$CURRENT_TIER" in
        tier1) TIER1_PASSED=$((TIER1_PASSED + 1)) ;;
        tier2) TIER2_PASSED=$((TIER2_PASSED + 1)) ;;
        tier3) TIER3_PASSED=$((TIER3_PASSED + 1)) ;;
    esac
}
log_fail()  {
    printf "${RED}[FAIL]${NC}  %s\n" "$1"
    FAILED=$((FAILED + 1))
    case "$CURRENT_TIER" in
        tier1) TIER1_FAILED=$((TIER1_FAILED + 1)) ;;
        tier2) TIER2_FAILED=$((TIER2_FAILED + 1)) ;;
        tier3) TIER3_FAILED=$((TIER3_FAILED + 1)) ;;
    esac
}
log_skip()  {
    printf "${BLUE}[SKIP]${NC}  %s\n" "$1"
    SKIPPED=$((SKIPPED + 1))
    case "$CURRENT_TIER" in
        tier1) TIER1_SKIPPED=$((TIER1_SKIPPED + 1)) ;;
        tier2) TIER2_SKIPPED=$((TIER2_SKIPPED + 1)) ;;
        tier3) TIER3_SKIPPED=$((TIER3_SKIPPED + 1)) ;;
    esac
}
log_info()  { printf "${BLUE}[INFO]${NC}  %s\n" "$1"; }

# ---------------------------------------------------------------------------
# Binary resolution
# ---------------------------------------------------------------------------
# Resolution priority (highest → lowest):
#   1. $AI_HARNESS_BINARY env var (for CI override)
#   2. ai-harness on PATH
resolve_binary() {
    if [ -n "${AI_HARNESS_BINARY:-}" ] && [ -x "$AI_HARNESS_BINARY" ]; then
        echo "$AI_HARNESS_BINARY"
        return 0
    fi
    if command -v ai-harness >/dev/null 2>&1; then
        echo "ai-harness"
        return 0
    fi
    echo ""
    return 1
}

# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

# cleanup_test_env — reset filesystem state between tests.
cleanup_test_env() {
    rm -rf "$HOME/.config/opencode" 2>/dev/null || true
    rm -rf "$HOME/.claude" 2>/dev/null || true
    rm -rf "$HOME/.agents" 2>/dev/null || true
    rm -rf "$HOME/.copilot" 2>/dev/null || true
    rm -rf "$HOME/.github" 2>/dev/null || true
    rm -rf "$HOME/.ai-harness" 2>/dev/null || true
    mkdir -p "$HOME/.config"
}

# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------

# assert_file_exists FILE LABEL
assert_file_exists() {
    local file="$1"
    local label="${2:-$file}"
    if [ -f "$file" ]; then
        log_pass "File exists: $label"
        return 0
    else
        log_fail "File NOT found: $label ($file)"
        return 1
    fi
}

# assert_file_not_exists FILE LABEL
assert_file_not_exists() {
    local file="$1"
    local label="${2:-$file}"
    if [ ! -f "$file" ]; then
        log_pass "File correctly absent: $label"
        return 0
    else
        log_fail "File should NOT exist: $label ($file)"
        return 1
    fi
}

# assert_dir_exists DIR LABEL
assert_dir_exists() {
    local dir="$1"
    local label="${2:-$dir}"
    if [ -d "$dir" ]; then
        log_pass "Directory exists: $label"
        return 0
    else
        log_fail "Directory NOT found: $label ($dir)"
        return 1
    fi
}

# assert_file_contains FILE PATTERN LABEL
assert_file_contains() {
    local file="$1"
    local pattern="$2"
    local label="${3:-$file contains '$pattern'}"
    if [ ! -f "$file" ]; then
        log_fail "Cannot check content — file not found: $file"
        return 1
    fi
    if grep -q "$pattern" "$file"; then
        log_pass "$label"
        return 0
    else
        log_fail "Pattern NOT found: '$pattern' in $file"
        return 1
    fi
}

# assert_file_not_contains FILE PATTERN LABEL
assert_file_not_contains() {
    local file="$1"
    local pattern="$2"
    local label="${3:-$file does NOT contain '$pattern'}"
    if [ ! -f "$file" ]; then
        log_pass "$label (file doesn't exist)"
        return 0
    fi
    if grep -q "$pattern" "$file"; then
        log_fail "Pattern FOUND (unexpected): '$pattern' in $file"
        return 1
    else
        log_pass "$label"
        return 0
    fi
}

# assert_file_size_min FILE BYTES LABEL
assert_file_size_min() {
    local file="$1"
    local min_bytes="$2"
    local label="${3:-$file >= $min_bytes bytes}"
    if [ ! -f "$file" ]; then
        log_fail "Cannot check size — file not found: $file"
        return 1
    fi
    local actual_size
    actual_size=$(wc -c < "$file" | tr -d ' ')
    if [ "$actual_size" -ge "$min_bytes" ]; then
        log_pass "$label (${actual_size}b)"
        return 0
    else
        log_fail "File too small: $file is ${actual_size}b, expected >= ${min_bytes}b"
        return 1
    fi
}

# assert_valid_json FILE LABEL
assert_valid_json() {
    local file="$1"
    local label="${2:-$file is valid JSON}"
    if [ ! -f "$file" ]; then
        log_fail "Cannot check JSON — file not found: $file"
        return 1
    fi
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c "import json; json.load(open('$file'))" 2>/dev/null; then
            log_pass "$label"
            return 0
        else
            log_fail "Invalid JSON: $file"
            return 1
        fi
    elif command -v jq >/dev/null 2>&1; then
        if jq '.' "$file" >/dev/null 2>&1; then
            log_pass "$label"
            return 0
        else
            log_fail "Invalid JSON: $file"
            return 1
        fi
    else
        log_skip "No JSON parser available to validate $file"
        return 0
    fi
}

# assert_output_contains OUTPUT PATTERN LABEL
assert_output_contains() {
    local output="$1"
    local pattern="$2"
    local label="${3:-output contains '$pattern'}"
    if echo "$output" | grep -qi "$pattern"; then
        log_pass "$label"
        return 0
    else
        log_fail "Output does NOT contain '$pattern'"
        return 1
    fi
}

# assert_output_not_contains OUTPUT PATTERN LABEL
assert_output_not_contains() {
    local output="$1"
    local pattern="$2"
    local label="${3:-output does NOT contain '$pattern'}"
    if echo "$output" | grep -qi "$pattern"; then
        log_fail "Output unexpectedly contains '$pattern'"
        return 1
    else
        log_pass "$label"
        return 0
    fi
}

# assert_md5_match FILE1 FILE2 LABEL
assert_md5_match() {
    local file1="$1"
    local file2="$2"
    local label="${3:-$file1 == $file2}"
    if [ ! -f "$file1" ]; then
        log_fail "Cannot compare — file not found: $file1"
        return 1
    fi
    if [ ! -f "$file2" ]; then
        log_fail "Cannot compare — file not found: $file2"
        return 1
    fi
    local hash1 hash2
    hash1=$(md5sum "$file1" | cut -d' ' -f1)
    hash2=$(md5sum "$file2" | cut -d' ' -f1)
    if [ "$hash1" = "$hash2" ]; then
        log_pass "$label"
        return 0
    else
        log_fail "Content mismatch: $file1 ($hash1) != $file2 ($hash2)"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    local tier_label="${1:-}"
    echo ""
    echo "========================================"
    echo "  E2E Test Summary"
    echo "  pattern: /home/diegoagd10/Projects/gentle-ai/e2e/e2e_test.sh"
    echo "========================================"
    echo "  --- Tier 1 (basic binary + routing) ---"
    printf "  ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" \
        "$TIER1_PASSED" "$TIER1_FAILED" "$TIER1_SKIPPED"
    echo "  --- Tier 2 (full lifecycle) ---"
    printf "  ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" \
        "$TIER2_PASSED" "$TIER2_FAILED" "$TIER2_SKIPPED"
    echo "  --- Tier 3 (backup/restore) ---"
    printf "  ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" \
        "$TIER3_PASSED" "$TIER3_FAILED" "$TIER3_SKIPPED"
    echo "  ========================================"
    echo "  OVERALL"
    printf "  ${GREEN}PASSED${NC}: %d  ${RED}FAILED${NC}: %d  ${BLUE}SKIPPED${NC}: %d\n" \
        "$PASSED" "$FAILED" "$SKIPPED"
    printf "  TOTAL : %d\n" "$((PASSED + FAILED + SKIPPED))"
    echo "========================================"

    if [ "$FAILED" -gt 0 ]; then
        printf "\n%bSome tests failed.%b\n" "$RED" "$NC"
        return 1
    fi

    printf "\n%bAll tests passed.%b\n" "$GREEN" "$NC"
    return 0
}
