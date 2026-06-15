#!/usr/bin/env bash
# Shared assertion helpers and pass/fail counters for the ai-harness e2e suite.
# Source this from a test script; it tracks PASSED/FAILED/SKIPPED and exposes
# small assert_* helpers that log a single line each. print_summary returns
# non-zero when any assertion failed, so the caller's exit code reflects it.

PASSED=0
FAILED=0
SKIPPED=0

_green()  { printf '\033[32m%s\033[0m' "$1"; }
_red()    { printf '\033[31m%s\033[0m' "$1"; }
_yellow() { printf '\033[33m%s\033[0m' "$1"; }

log_section() { printf '\n=== %s ===\n' "$1"; }
log_pass()    { PASSED=$((PASSED + 1)); printf '  %s %s\n' "$(_green '✓')" "$1"; }
log_skip()    { SKIPPED=$((SKIPPED + 1)); printf '  %s %s\n' "$(_yellow '⊘')" "$1"; }
log_fail() {
  FAILED=$((FAILED + 1))
  printf '  %s %s\n' "$(_red '✗')" "$1"
  [ -n "${2:-}" ] && printf '      %s\n' "$2"
  return 0
}

# assert_file_exists PATH LABEL — passes when PATH exists (file, dir, or link).
assert_file_exists() {
  if [ -e "$1" ]; then log_pass "$2"; else log_fail "$2" "missing: $1"; fi
}

# assert_not_symlink PATH LABEL — passes when PATH exists and is not a symlink.
assert_not_symlink() {
  if [ ! -e "$1" ]; then
    log_fail "$2" "missing: $1"
  elif [ -L "$1" ]; then
    log_fail "$2" "unexpected symlink: $1"
  else
    log_pass "$2"
  fi
}

# assert_valid_json PATH LABEL — passes when PATH parses as JSON.
assert_valid_json() {
  if python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$1" 2>/dev/null; then
    log_pass "$2"
  else
    log_fail "$2" "invalid JSON: $1"
  fi
}

# assert_file_contains PATH LITERAL LABEL — passes when PATH contains LITERAL.
assert_file_contains() {
  if grep -qF -- "$2" "$1" 2>/dev/null; then log_pass "$3"; else log_fail "$3" "$1 missing literal: $2"; fi
}

# assert_file_not_contains PATH LITERAL LABEL — passes when PATH lacks LITERAL.
assert_file_not_contains() {
  if grep -qF -- "$2" "$1" 2>/dev/null; then log_fail "$3" "$1 unexpectedly contains: $2"; else log_pass "$3"; fi
}

# assert_output_contains LABEL NEEDLE CMD... — runs CMD, passes when its combined
# stdout+stderr contains NEEDLE. Uses a here-string (not a pipe) so a -q match
# never trips `set -o pipefail` via SIGPIPE on the producer.
assert_output_contains() {
  local label="$1" needle="$2"; shift 2
  local out; out=$("$@" 2>&1)
  if grep -qF -- "$needle" <<<"$out"; then
    log_pass "$label"
  else
    log_fail "$label" "output missing '$needle' (cmd: $*)"
  fi
}

# assert_str_contains LABEL HAYSTACK NEEDLE — passes when HAYSTACK contains the
# literal NEEDLE. Here-string keeps `set -o pipefail` from misfiring on -q.
assert_str_contains() {
  if grep -qF -- "$3" <<<"$2"; then log_pass "$1"; else log_fail "$1" "missing: $3"; fi
}

# assert_cmd_succeeds LABEL CMD... — passes when CMD exits 0.
assert_cmd_succeeds() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then log_pass "$label"; else log_fail "$label" "command failed: $*"; fi
}

print_summary() {
  printf '\n----------------------------------------\n'
  printf 'PASSED=%d FAILED=%d SKIPPED=%d\n' "$PASSED" "$FAILED" "$SKIPPED"
  [ "$FAILED" -eq 0 ]
}
