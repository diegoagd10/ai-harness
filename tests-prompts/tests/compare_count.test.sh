#!/usr/bin/env bash
# compare_count.test.sh — verifies the compare_count helper inside
# tests-prompts/run.sh + the parse_csv() delegation to tests-prompts/parse_csv.py.
#
# Strategy:
#   - Extract compare_count() definition from run.sh via awk.
#   - Run the function with various (got, exp) pairs in clean subshells.
#   - Add a static check that the per-row block has no raw [ -ne ] form.
#   - Add a static check that run.sh references tests-prompts/parse_csv.py.
#
# Scenarios covered (subtasks 4.1 – 4.10):
#   4.1  helper defined with right signature
#   4.2  non-integer exp → labeled [FAIL] without invoking -ne
#   4.3  per-row block → bash integer-error noise gone
#   4.4  integer-unequal → labeled [FAIL] naming both values
#   4.5  integer-equal → exit 0 silently
#   4.6  per-row block has three compare_count calls (tools/skills/subs)
#   4.7  raw [ $got_X -ne $exp_X ] form is removed from per-row block
#   4.8  run.sh parse_csv delegates to tests-prompts/parse_csv.py
#   4.9  run.sh header documents RFC-4180 CSV contract
#   4.10 run.sh header names the silent-pass and opaque-fail failure modes

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_SH="$SCRIPT_DIR/../run.sh"
PARSER_PY="$SCRIPT_DIR/../parse_csv.py"

if [ ! -f "$RUN_SH" ]; then
    printf '[FAIL] run.sh not found at %s\n' "$RUN_SH" >&2
    exit 1
fi

# Extract compare_count() { ... } block from run.sh.
fn_def="$(awk '
    /^compare_count\(\) \{$/ { capture = 1; print; next }
    capture { print; if ($0 == "}") exit }
' "$RUN_SH")"

if [ -z "$fn_def" ] || ! printf '%s\n' "$fn_def" | grep -q '^compare_count() {$'; then
    printf '[FAIL] could not locate compare_count() in %s\n' "$RUN_SH" >&2
    exit 1
fi

FAIL=0

# 4.1 — helper defined with expected signature: 5 positional args.
expect_signature_match() {
    # Header line must start at column 0.
    if ! printf '%s\n' "$fn_def" | head -1 | grep -qE '^compare_count\(\) \{$'; then
        printf '  [FAIL] 4.1 compare_count signature mismatch (header: %q)\n' \
            "$(printf '%s\n' "$fn_def" | head -1)" >&2
        FAIL=$((FAIL + 1))
        return
    fi
    # Body must reference exactly 5 positional args (label, got, exp, prompt, row_idx).
    for slot in 'label="$1"' 'got="$2"' 'exp="$3"' 'prompt="$4"' 'row_idx="$5"'; do
        if ! printf '%s\n' "$fn_def" | grep -qF "$slot"; then
            printf '  [FAIL] 4.1 compare_count missing positional arg %q\n' "$slot" >&2
            FAIL=$((FAIL + 1))
        fi
    done
}
expect_signature_match

# 4.5 — integer equal returns 0 silently.
expect_equal_silent() {
    local label="$1" expected_rc="$2" body="$3"
    local rc stderr_actual
    stderr_actual=$(bash -c "${fn_def}; ${body}" 2>&1 >/dev/null)
    rc=$?
    if [ "$rc" -ne "$expected_rc" ]; then
        printf '  [FAIL] %s: expected exit=%s, got exit=%s\n  stderr: %q\n' \
            "$label" "$expected_rc" "$rc" "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
    if [ -n "$stderr_actual" ]; then
        printf '  [FAIL] %s: expected silent, got stderr=%q\n' \
            "$label" "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
}
expect_equal_silent "4.5 integer-equal returns 0 silently" 0 \
    'compare_count tools 3 3 "hello" 1'

# 4.4 — integer-unequal returns 1 with labeled [FAIL] naming both values.
expect_unequal_labeled() {
    local body="$1" exp_val="$2" got_val="$3"
    local rc stderr_actual
    stderr_actual=$(bash -c "${fn_def}; ${body}" 2>&1 >/dev/null)
    rc=$?
    if [ "$rc" -ne 1 ]; then
        printf '  [FAIL] 4.4 expected exit=1, got exit=%s\n' "$rc" >&2
        FAIL=$((FAIL + 1))
    fi
    if [[ "$stderr_actual" != *"[FAIL] row 1 (hello): tools"* ]]; then
        printf '  [FAIL] 4.4 stderr missing labeled [FAIL] row 1 (hello): tools\n  got: %q\n' \
            "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
    if [[ "$stderr_actual" != *"expected ${exp_val}"* ]] || [[ "$stderr_actual" != *"got ${got_val}"* ]]; then
        printf '  [FAIL] 4.4 stderr must name both values: expected %s, got %s\n  got: %q\n' \
            "$exp_val" "$got_val" "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
}
expect_unequal_labeled 'compare_count tools 0 7 "hello" 1' 7 0

# 4.2 + 4.3 — non-integer exp produces labeled [FAIL] without invoking -ne
# (so bash's `integer expression expected` noise must be absent).
expect_non_integer() {
    local body="$1" expected_row="$2" expected_exp_value="$3"
    local rc stderr_actual
    stderr_actual=$(bash -c "${fn_def}; ${body}" 2>&1 >/dev/null)
    rc=$?
    if [ "$rc" -ne 1 ]; then
        printf '  [FAIL] 4.2 expected exit=1, got exit=%s\n' "$rc" >&2
        FAIL=$((FAIL + 1))
    fi
    if [[ "$stderr_actual" != *"[FAIL] row ${expected_row} (hello): tools"* ]]; then
        printf '  [FAIL] 4.2 stderr missing labeled [FAIL] row %s (hello): tools\n  got: %q\n' \
            "$expected_row" "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
    if [[ "$stderr_actual" != *"${expected_exp_value}"* ]]; then
        printf '  [FAIL] 4.2 stderr must name the offending exp value %q verbatim\n  got: %q\n' \
            "$expected_exp_value" "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
    if [[ "$stderr_actual" == *"integer expression expected"* ]]; then
        printf '  [FAIL] 4.3 stderr must NOT contain bash "integer expression expected"\n  got: %q\n' \
            "$stderr_actual" >&2
        FAIL=$((FAIL + 1))
    fi
}
expect_non_integer 'compare_count tools 0 "how are you doing?" "hello" 2' 2 "how are you doing?"
expect_non_integer 'compare_count tools 0 "como estas?" "hello" 3' 3 "como estas?"

# 4.6 — per-row block has three compare_count calls (one each for tools, skills, subs).
expected_labels=(tools skills subs)
for label in "${expected_labels[@]}"; do
    if ! grep -nE "^[[:space:]]*compare_count[[:space:]]+$label" "$RUN_SH" >/dev/null; then
        printf '  [FAIL] 4.6 missing compare_count call for label %q in run.sh\n' "$label" >&2
        FAIL=$((FAIL + 1))
    fi
done

# 4.7 — raw [ $got_X -ne $exp_X ] form is gone from the per-row block.
if grep -nE '\[ *"\$got_(tools|skills|subs)" *-[ne]+ *"\$exp_' "$RUN_SH" >/dev/null; then
    printf '  [FAIL] 4.7 raw [ $got_X -ne $exp_X ] form still present in run.sh\n' >&2
    grep -nE '\[ *"\$got_(tools|skills|subs)"' "$RUN_SH" >&2 || true
    FAIL=$((FAIL + 1))
fi

# 4.8 — run.sh parse_csv() delegates to tests-prompts/parse_csv.py.
if ! grep -qE 'parse_csv\.py' "$RUN_SH"; then
    printf '  [FAIL] 4.8 run.sh does not reference parse_csv.py (delegation missing)\n' >&2
    FAIL=$((FAIL + 1))
fi

# Functional: run.sh's parse_csv() invoked on a minimal well-formed CSV must
# emit the expected NUL/TAB record. We source run.sh in a subshell with cwd
# set to tests-prompts/ so the relative path resolves, then call parse_csv.
parser_fn="$(awk '
    /^parse_csv\(\) \{$/ { capture = 1; print; next }
    capture { print; if ($0 == "}") exit }
' "$RUN_SH")"
if [ -z "$parser_fn" ]; then
    printf '  [FAIL] 4.8 could not extract parse_csv() from run.sh\n' >&2
    FAIL=$((FAIL + 1))
else
    work_csv="$(mktemp --suffix=.csv)"
    actual_bin="$(mktemp)"
    trap 'rm -f "$work_csv" "$actual_bin"' EXIT
    printf 'prompt, tools calls (number), skills calls (number), sub-agent calls (number)\nhello,0,0,0\n' > "$work_csv"
    pushd "$SCRIPT_DIR/.." >/dev/null
    # SCRIPT_DIR inside the function must point at tests-prompts/ (where
    # parse_csv.py lives), not tests-prompts/tests/.
    parser_dir="$(cd "$SCRIPT_DIR/.." && pwd)"
    bash -c "SCRIPT_DIR='$parser_dir'; ${parser_fn}; parse_csv '$work_csv'" \
        > "$actual_bin" 2>/dev/null
    popd >/dev/null
    # Compare raw bytes via Python (bash strips NUL from command substitution,
    # so `[ "$actual" = "$expected" ]` would falsely report MATCH).
    python3 - "$actual_bin" <<'PYCHECK'
import sys
expected = b"hello\t0\t0\t0\0"
actual_path = sys.argv[1]
with open(actual_path, "rb") as f:
    actual = f.read()
if actual != expected:
    sys.stderr.write(f"expected: {expected!r}\nactual:   {actual!r}\n")
    sys.exit(1)
sys.exit(0)
PYCHECK
    py_rc=$?
    if [ "$py_rc" -ne 0 ]; then
        printf '  [FAIL] 4.8 run.sh parse_csv() did not emit expected NUL/TAB record\n' >&2
        FAIL=$((FAIL + 1))
    fi
fi

# 4.9 + 4.10 — header comment documents RFC-4180 contract + failure modes.
header_block="$(head -40 "$RUN_SH")"
if ! printf '%s' "$header_block" | grep -qE 'RFC.?4180'; then
    printf '  [FAIL] 4.9 run.sh header does not document RFC-4180 CSV contract\n' >&2
    FAIL=$((FAIL + 1))
fi
# Silent-pass phrase OR equivalent.
if ! printf '%s' "$header_block" | grep -qE 'silent(-|ly )?pass'; then
    printf '  [FAIL] 4.10 run.sh header does not name the silent-pass failure mode\n' >&2
    FAIL=$((FAIL + 1))
fi
# Opaque-fail phrase: bash integer-error message.
if ! printf '%s' "$header_block" | grep -qE 'integer expression expected'; then
    printf '  [FAIL] 4.10 run.sh header does not name the opaque-fail (integer expression expected) mode\n' >&2
    FAIL=$((FAIL + 1))
fi

# Also confirm parse_csv.py is on disk (in case the delegation test is the only
# way the parser is reached; we already proved it in task 2's tests but repeat
# the assertion for self-containment here).
if [ ! -f "$PARSER_PY" ]; then
    printf '  [FAIL] 4.8 parse_csv.py not on disk at %s\n' "$PARSER_PY" >&2
    FAIL=$((FAIL + 1))
fi

if [ "$FAIL" -gt 0 ]; then
    printf '\n[FAIL] %d sub-scenario(s) failed\n' "$FAIL" >&2
    exit 1
fi

printf '[OK] all compare_count + delegation sub-scenarios passed\n'
exit 0
