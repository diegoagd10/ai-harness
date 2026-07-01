#!/usr/bin/env bash
# tests-prompts/tests/run_sh_order.test.sh — function ordering
# regression detector for tests-prompts/run.sh.
#
# The bug class: bash does NOT hoist function definitions the way some
# readers assume. A function MUST be defined BEFORE its first top-level
# call site, or the interpreter reports `<func>: command not found` at
# that call site. Earlier fix-loops for fix-tests-prompts-assertions
# introduced `parse_csv` at line 230 while the runner called it at line
# 115; the in-container build then exploded with
# `parse_csv: command not found` before any row ran (validator finding
# reported in .ai-harness/changes/.../validation.md).
#
# This test pins the rule as a static check on run.sh. Runs in <50ms,
# no Docker, no model.
#
# Sub-scenarios:
#   L1  parse_csv() { definition line < first top-level invocation line
#   L2  assert_container_required() { definition line < first call line
#       (Track B invariant — guard must precede any bootstrap)
#   L3  Behavioral: source parse_csv extracted from run.sh + call it
#       against a minimal well-formed CSV. This proves the function
#       extracted from run.sh is actually callable end-to-end, not just
#       textually present. (Catches a regression where parse_csv() is
#       defined but broken — e.g. body rewritten to nothing.)
#
# Exit codes:
#   0 — every sub-scenario passed
#   non-zero — at least one ordering or behavioral assertion failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SH="$SCRIPT_DIR/../run.sh"

FAIL=0
ok()   { printf '  [OK]   %s\n' "$1"; }
mark() { printf '  [FAIL] %s\n' "$1" >&2; FAIL=$((FAIL + 1)); }

# ---------------------------------------------------------------------------
# L1 — parse_csv() { definition line < first top-level invocation line.
#
# Exclude:
#   - comment lines (start with # after the line number prefix)
#   - the function definition line itself (parse_csv() {)
#   - the function body line that mentions parse_csv.py
# ---------------------------------------------------------------------------
def_line=$(grep -nE '^parse_csv\(\) \{' "$RUN_SH" | head -1 | cut -d: -f1)
call_line=$(grep -nE '\bparse_csv\b' "$RUN_SH" \
    | grep -vE '^[[:digit:]]+:[[:space:]]*#' \
    | grep -vE '^[[:digit:]]+:parse_csv\(\)' \
    | grep -vE '^[[:digit:]]+:.+python3[[:space:]]' \
    | head -1 \
    | cut -d: -f1)

if [ -z "$def_line" ]; then
    mark "L1 parse_csv() { definition not found in run.sh"
elif [ -z "$call_line" ]; then
    mark "L1 parse_csv top-level invocation not found in run.sh"
elif [ "$def_line" -lt "$call_line" ]; then
    ok "L1 parse_csv() { (line $def_line) precedes invocation (line $call_line)"
else
    mark "L1 parse_csv() { (line $def_line) does NOT precede invocation (line $call_line) — bash will fail with 'parse_csv: command not found' at line $call_line"
fi

# ---------------------------------------------------------------------------
# L2 — assert_container_required() { definition line < first call line.
# ---------------------------------------------------------------------------
guard_def=$(grep -nE '^assert_container_required\(\) \{' "$RUN_SH" | head -1 | cut -d: -f1)
guard_call=$(grep -nE '^assert_container_required$' "$RUN_SH" | head -1 | cut -d: -f1)

if [ -z "$guard_def" ]; then
    mark "L2 assert_container_required() { definition not found in run.sh"
elif [ -z "$guard_call" ]; then
    mark "L2 assert_container_required top-level call not found in run.sh"
elif [ "$guard_def" -lt "$guard_call" ]; then
    ok "L2 assert_container_required() { (line $guard_def) precedes call (line $guard_call)"
else
    mark "L2 assert_container_required() { (line $guard_def) does NOT precede call (line $guard_call)"
fi

# ---------------------------------------------------------------------------
# L3 — Behavioral: extract parse_csv from run.sh, source it, invoke it
# against a minimal well-formed CSV. This proves the function extracted
# from run.sh is callable end-to-end (catches a regression where the
# function exists textually but its body is broken).
#
# Mirrors the technique in tests-prompts/tests/compare_count.test.sh::4.8.
# ---------------------------------------------------------------------------
parser_dir="$SCRIPT_DIR/.."
work_csv="$(mktemp -t run_sh_order.XXXXXX.csv)"
trap 'rm -f "$work_csv"' EXIT

printf 'prompt, tools calls (number), skills calls (number), sub-agent calls (number)\nhello,0,0,0\n' > "$work_csv"

parser_fn="$(awk '
    /^parse_csv\(\) \{$/ { capture = 1; print; next }
    capture && /^}/      { print; capture = 0; next }
    capture              { print }
' "$RUN_SH")"

if [ -z "$parser_fn" ]; then
    mark "L3 could not extract parse_csv() { ... } from run.sh"
else
    # Write stdout/stderr to files so we don't trip bash's
    # "ignored null byte in input" warning when the record contains a
    # NUL terminator.
    out_file="$(mktemp -t run_sh_order.out.XXXXXX)"
    err_file="$(mktemp -t run_sh_order.err.XXXXXX)"
    trap 'rm -f "$work_csv" "$out_file" "$err_file"' EXIT
    set +e
    bash -c "SCRIPT_DIR='$parser_dir'; ${parser_fn}; parse_csv '$work_csv'" \
        > "$out_file" 2> "$err_file"
    rc=$?
    set -e
    # Expect exactly the record hello<TAB>0<TAB>0<TAB>0<NUL> on stdout.
    # Use od (POSIX) for byte-level inspection — works without xxd.
    hex=$(od -An -tx1 -N12 "$out_file" 2>/dev/null | tr -d ' \n')
    expected='68656c6c6f'   # hello
    expected+='09'          # TAB
    expected+='30'          # 0
    expected+='09'
    expected+='30'
    expected+='09'
    expected+='30'
    expected+='00'          # NUL
    if [ "$rc" -eq 0 ] && [ "$hex" = "$expected" ]; then
        ok "L3 parse_csv sourced from run.sh + invoked on $work_csv returned rc=0 with hello\\t0\\t0\\t0\\0 record (12 bytes)"
    else
        err_text=$(cat "$err_file" 2>/dev/null || true)
        mark "L3 parse_csv sourced from run.sh + invoked on $work_csv returned rc=$rc (expected 0); hex=$hex expected=$expected; stderr=$err_text"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if [ "$FAIL" -gt 0 ]; then
    printf '\n[FAIL] %d ordering sub-scenario(s) failed\n' "$FAIL" >&2
    exit 1
fi
printf '\n[OK] all run_sh_order sub-scenarios passed\n'
exit 0