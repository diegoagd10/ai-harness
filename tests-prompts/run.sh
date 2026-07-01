#!/usr/bin/env bash
# run.sh — in-container prompt-test runner.
#
# Reads cases.csv from /tests-prompts/cases.csv, prepares a writable
# workspace from /source-ro, installs ai-harness from the workspace,
# registers the change-orchestrator agent into opencode, then runs one
# fresh `opencode run` per CSV row.
#
# Per-row results are aggregated; the script exits 0 only if every row
# passed. Failure traces land in /logs/ (mounted from the host).
#
# Public seam: tests-prompts/run.sh (this file).
# Internal helpers:
#   - parse_csv            (inline) — row-shape-aware CSV parser; thin
#                           wrapper around tests-prompts/parse_csv.py
#                           so the in-container call site is one bash
#                           line. Defined ABOVE its first invocation
#                           (validate-cases-csv block) — bash does NOT
#                           hoist function definitions, so an order
#                           swap explodes with `parse_csv: command
#                           not found` before row 1. See
#                           tests-prompts/tests/run_sh_order.test.sh.
#   - assert_container_required (inline) — refuses host-side runs that
#                           would mutate $HOME/.ai-harness, .config/opencode,
#                           etc. See isolate-host-config-from-test-runs spec.
#   - extract_counts       (tests-prompts/_extractor.py) — schema lives
#                           HERE ONLY; everything else consumes the
#                           returned triple.
#   - slugify              (inline) — fs-safe prompt prefix
#   - dump_failure_trace   (inline) — writes failure-only /logs/<row>-<slug>.json
#   - run_row              (inline) — per-row opencode invocation adapter
#
# CSV contract (RFC-4180): prompts containing commas, quotes, or newlines
# MUST be RFC-4180 quoted in cases.csv. Unquoted commas shift expected-count
# columns silently — the comparison block either fails opaquely
# (`bash: integer expression expected`) OR, worse, passes silently when the
# shifted value happens to be an integer that matches the orchestrator's
# tool count. The validate-csv-row-shape parser catches the silent-pass
# class at parse time; this comment is here so the next contributor who
# edits cases.csv reads the rule before they break it.
set -uo pipefail

# Resolve the directory this script lives in. Used by parse_csv() to
# locate tests-prompts/parse_csv.py regardless of cwd. Works in both the
# container (SCRIPT_DIR=/tests-prompts) and on the host (SCRIPT_DIR is
# the absolute tests-prompts path under the repo root).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# assert_container_required — host-mutation guard.
#
# Closes Track B of fix-tests-prompts-assertions at its source: refusing to
# run on the host altogether means no host path can be mutated, regardless
# of which one `ai-harness install -o opencode` or cleanup_test_env would
# have touched. Path-by-path backup/restore was rejected as a shallower
# alternative in design.md.
#
# Container signals (passes if ANY is true, evaluated in order):
#   1. $CONTAINER_REQUIRED_OK == "1"             — escape hatch for host
#                                                  development of the runner
#                                                  itself (docker-test.sh
#                                                  sets it inside the
#                                                  container; devs iterating
#                                                  on run.sh directly can
#                                                  set it manually).
#   2. $CONTAINER_RUN_MARKER (default: /run/.containerenv) — Podman / CRI-O.
#   3. $CONTAINER_DOCKER_MARKER (default: /.dockerenv)   — Docker.
#   4. $CONTAINER_CGROUP_PATH   (default: /proc/1/cgroup) — cgroup fallback
#      must be readable AND contain 'docker' or 'containerd'.
#
# If none of those signals pass: write [FATAL] to stderr and exit 2.
#
# The CONTAINER_*_MARKER and CONTAINER_CGROUP_PATH env vars exist both
# for testing (we cannot create /.dockerenv without root) and for
# non-standard runtimes that want to plug their own markers in.
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
    printf '[FATAL] refusing to run on the host: tests-prompts must be invoked via docker-test.sh\n' >&2
    exit 2
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CASES_CSV="${CASES_CSV:-/tests-prompts/cases.csv}"
SOURCE_RO="${SOURCE_RO:-/source-ro}"
WORKSPACE="${WORKSPACE:-/workspace}"
LOGS_DIR="${LOGS_DIR:-/logs}"
PINNED_MODEL="${PINNED_MODEL:-minimax/minimax-m3}"
OPENCODE_BIN="${OPENCODE_BIN:-opencode}"
AGENT_NAME="${AGENT_NAME:-change-orchestrator}"
EXTRACTOR="${EXTRACTOR:-/tests-prompts/_extractor.py}"

mkdir -p "$LOGS_DIR"

# ---------------------------------------------------------------------------
# Host-mutation guard: this script writes to $HOME paths via
# `ai-harness install -o opencode` and (transitively) the host-bootstrap
# helper. Refuse the entire script on a non-container host so no host
# config is mutated. See assert_container_required() at the top of this
# file. The guard must pass BEFORE the bootstrap copy below.
# ---------------------------------------------------------------------------
assert_container_required

# ---------------------------------------------------------------------------
# parse_csv <path> — streams CSV rows as TAB-fielded, NUL-terminated records
# on stdout. One record per non-blank data row:
#   <prompt>\t<tools>\t<skills>\t<subs>\0
#
# Defined HERE (above the first invocation below) because bash does NOT
# hoist function definitions. Earlier fix-loops added this helper at
# line ~230 of this file while the first call site is at the top of the
# validate-cases-csv block; the in-container build then exploded with
# `parse_csv: command not found` before row 1. Pinning the definition
# next to its first use makes that ordering self-evident.
#
# Delegates to tests-prompts/parse_csv.py (the validate-csv-row-shape seam)
# which owns row-shape correctness: trailing-field shifts, non-integer
# counts, empty prompts all produce a labeled [PARSE-FAIL] line on stderr
# and a non-zero exit. The original bug was a heredoc that quietly
# `or "0"` defaulted missing cells — the seam exists so that class of
# failure can't reach the per-row loop.
# ---------------------------------------------------------------------------
parse_csv() {
    local path="$1"
    python3 "$SCRIPT_DIR/parse_csv.py" "$path"
}

# ---------------------------------------------------------------------------
# Validate cases.csv BEFORE any expensive bootstrap. The parser
# (tests-prompts/parse_csv.py) emits [PARSE-FAIL] lines on stderr and
# exits non-zero on row-shape errors. Catch that exit code here so the
# suite cannot silently pass on broken data — a row the parser rejects
# would otherwise produce zero records, the per-row loop would skip
# silently, and OVERALL_RC would stay 0.
# ---------------------------------------------------------------------------
PARSED="$(mktemp)"
parse_err="$(mktemp)"
if ! parse_csv "$CASES_CSV" > "$PARSED" 2> "$parse_err"; then
    cat "$parse_err" >&2
    # Mirror dump_failure_trace: write a structured JSON artifact into
    # $LOGS_DIR so CI scrapers and humans see the same artifact shape
    # whether the failure was a parse-csv rejection or a per-row PASS/FAIL.
    # Best-effort: a helper failure must NOT mask the existing exit-1
    # path or the labeled [PARSE-FAIL] line above. See
    # tests-prompts/_dump_parse_trace.py for the seam.
    if ! python3 "$SCRIPT_DIR/_dump_parse_trace.py" "$LOGS_DIR" "$parse_err" 2>/dev/null; then
        printf '[WARN] could not write parse-fail trace to %s\n' "$LOGS_DIR" >&2
    fi
    printf '[FAIL] cases.csv rejected by parse_csv — see [PARSE-FAIL] above\n' >&2
    rm -f "$PARSED" "$parse_err"
    exit 1
fi
rm -f "$parse_err"

# ---------------------------------------------------------------------------
# Bootstrap: copy /source-ro -> /workspace, install ai-harness, register agent
# ---------------------------------------------------------------------------
printf '[BOOTSTRAP] copying %s -> %s\n' "$SOURCE_RO" "$WORKSPACE" >&2
if ! cp -a "$SOURCE_RO" "$WORKSPACE"; then
    printf '[FAIL] workspace copy failed (%s -> %s)\n' "$SOURCE_RO" "$WORKSPACE" >&2
    exit 1
fi

cd "$WORKSPACE" || { printf '[FAIL] cd %s failed\n' "$WORKSPACE" >&2; exit 1; }

printf '[BOOTSTRAP] uv tool install . (python3)\n' >&2
if ! uv tool install . --python python3; then
    printf '[FAIL] uv tool install . failed — workspace is not a valid Python project\n' >&2
    exit 1
fi

# Make the freshly-installed binary resolvable. uv tool install places
# scripts under UV_TOOL_BIN_DIR (default /root/.local/bin); the canonical
# installer already adds ~/.local/bin to PATH, but be defensive.
export PATH="$HOME/.local/bin:/root/.local/bin:${PATH}"
if ! command -v ai-harness >/dev/null 2>&1; then
    printf '[FAIL] ai-harness not on PATH after uv tool install .\n' >&2
    exit 1
fi

printf '[BOOTSTRAP] ai-harness install -o opencode\n' >&2
if ! ai-harness install -o opencode; then
    printf '[FAIL] ai-harness install -o opencode failed\n' >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Capture opencode version (CLI-shape break detection — fail loud early)
# ---------------------------------------------------------------------------
printf '[VERSION] ' >&2
"$OPENCODE_BIN" --version >&2 || printf 'unavailable' >&2
printf '\n' >&2

# ---------------------------------------------------------------------------
# Helpers — non-JSON, no schema knowledge here.
# ---------------------------------------------------------------------------

# slugify <prompt> — fs-safe prefix used in failure trace filenames.
# Rules: keep [A-Za-z0-9_-]; everything else collapses to '-'; repeats of
# '-' collapse; leading/trailing '-' stripped; capped at 32 chars.
slugify() {
    local s="$1"
    s=$(printf '%s' "$s" | tr -c 'A-Za-z0-9_-' '-')
    s=$(printf '%s' "$s" | tr -s '-' '-')
    s=$(printf '%s' "$s" | sed 's/^-*//; s/-*$//')
    s=${s:0:32}
    [ -z "$s" ] && s="row"
    printf '%s' "$s"
}

# dump_failure_trace <row_index> <prompt> <trace_text>
# Writes the trace verbatim to $LOGS_DIR/<row_index>-<slug>.json.
dump_failure_trace() {
    local row_index="$1"
    local prompt="$2"
    local trace_text="$3"
    local slug
    slug=$(slugify "$prompt")
    local fname="${row_index}-${slug}.json"
    # Final filename sanitization (defensive — slugify should already be safe).
    fname=$(printf '%s' "$fname" | tr -c 'A-Za-z0-9._-' '-')
    # Hard 64-char cap per failure-trace-dump spec.
    [ "${#fname}" -gt 64 ] && fname="${fname:0:64}"
    printf '%s' "$trace_text" > "$LOGS_DIR/$fname"
}

# run_row <row_index> <prompt> — invokes one fresh `opencode run` process.
# Prints the raw stdout (JSON event stream) to stdout.
run_row() {
    local row_index="$1"
    local prompt="$2"
    # shellcheck disable=SC2086  # PINNED_MODEL is a single token
    "$OPENCODE_BIN" run \
        --agent "$AGENT_NAME" \
        --auto \
        --format json \
        --model "$PINNED_MODEL" \
        --dir "$WORKSPACE" \
        --title "prompt-tests-row-${row_index}" \
        "$prompt" 2>/dev/null
    return $?
}

# compare_count <label> <got> <exp> <prompt> <row_idx>
#
# Integer-guarded assertion helper for one count column in the per-row
# block. Replaces the bare `[ "$got" -ne "$exp" ]` form which silently
# swallows `bash: integer expression expected` when the parsed expected
# value is a non-integer string (the original bug). On success returns
# 0 silently; on failure returns 1 and writes a labeled [FAIL] line on
# stderr naming the row, prompt, label, both values, and the reason.
#
# Two failure modes:
#   - non-integer `exp`         → "- non-integer expected: <exp>"
#     regex check fires BEFORE any arithmetic, so `-ne` is never invoked
#     on a non-integer — bash's "integer expression expected" noise is
#     impossible.
#   - integer but not equal     → "calls expected <exp> got <got>"
compare_count() {
    local label="$1"
    local got="$2"
    local exp="$3"
    local prompt="$4"
    local row_idx="$5"

    if ! [[ "$exp" =~ ^[0-9]+$ ]]; then
        printf '[FAIL] row %d (%s): %s expected %s got %s — non-integer expected\n' \
            "$row_idx" "$prompt" "$label" "$exp" "$got" >&2
        return 1
    fi

    if [ "$got" -ne "$exp" ]; then
        printf '[FAIL] row %d (%s): %s expected %s got %s\n' \
            "$row_idx" "$prompt" "$label" "$exp" "$got" >&2
        return 1
    fi

    return 0
}

# ---------------------------------------------------------------------------
# Per-row loop
# ---------------------------------------------------------------------------
# Total = number of NULs in parse_csv's stdout (one NUL per record).
# The PARSED file was validated and materialised above; re-use it so we
# don't re-parse the CSV on every TOTAL/loop call.
TOTAL=$(tr -cd '\0' < "$PARSED" | wc -c | tr -d '[:space:]')
PASSED=0
FAILED=0
OVERALL_RC=0
ROW_INDEX=0

# `read -d ''` reads up to the next NUL byte (or EOF). With IFS=$'\t' the
# fields within a record are split on TAB. Each iteration consumes exactly
# one CSV record even if its prompt contains newlines.
while IFS=$'\t' read -r -d '' PROMPT EXP_TOOLS EXP_SKILLS EXP_SUBAGENTS; do
    ROW_INDEX=$((ROW_INDEX + 1))

    trace_text=$(run_row "$ROW_INDEX" "$PROMPT" || true)
    [ -z "$trace_text" ] && trace_text=""

    counts=$(printf '%s' "$trace_text" | python3 "$EXTRACTOR" 2>/dev/null || printf '0 0 0')
    got_tools=$(printf '%s' "$counts"  | awk '{print $1}')
    got_skills=$(printf '%s' "$counts" | awk '{print $2}')
    got_subs=$(printf '%s' "$counts"   | awk '{print $3}')

    # Coerce expected counts to int (strip whitespace, default 0).
    exp_tools=$(printf '%s' "$EXP_TOOLS"     | tr -d '[:space:]'); exp_tools=${exp_tools:-0}
    exp_skills=$(printf '%s' "$EXP_SKILLS"   | tr -d '[:space:]'); exp_skills=${exp_skills:-0}
    exp_subs=$(printf '%s' "$EXP_SUBAGENTS"  | tr -d '[:space:]'); exp_subs=${exp_subs:-0}

    row_rc=0
    compare_count tools  "$got_tools"  "$exp_tools"  "$PROMPT" "$ROW_INDEX" || row_rc=1
    compare_count skills "$got_skills" "$exp_skills" "$PROMPT" "$ROW_INDEX" || row_rc=1
    compare_count subs   "$got_subs"   "$exp_subs"   "$PROMPT" "$ROW_INDEX" || row_rc=1

    if [ "$row_rc" -eq 0 ]; then
        printf '[CASE %d/%d] PASS\n' "$ROW_INDEX" "$TOTAL" >&2
        PASSED=$((PASSED + 1))
    else
        printf '[CASE %d/%d] FAIL\n' "$ROW_INDEX" "$TOTAL" >&2
        dump_failure_trace "$ROW_INDEX" "$PROMPT" "$trace_text"
        FAILED=$((FAILED + 1))
        OVERALL_RC=1
    fi
done < "$PARSED"

rm -f "$PARSED"

printf '[SUMMARY] passed=%d failed=%d total=%d\n' "$PASSED" "$FAILED" "$TOTAL" >&2

# ---------------------------------------------------------------------------
# CASES_CSV_E2E second loop — opt-in RED regression surface.
#
# Activated only when CASES_CSV_E2E is set and non-empty. For each row
# in the E2E CSV:
#   1. Run a fresh `opencode run` (same shape as the first loop).
#   2. ALWAYS dump the raw trace to $LOGS_DIR/<row>-<slug>.json — the
#      smoke loop only writes on FAIL, the RED loop writes on PASS too
#      so the trace is available for debugging regressions.
#   3. Pipe the trace through tests-prompts/_e2e_runner.py for the
#      per-fixture routing decision (the three flat predicates from
#      _e2e_assertions.py are composed per fixture there).
#   4. Print `[E2E-ASSERT] fixture=<slug> row=<n> pass|fail` and
#      aggregate pass/fail into E2E_RC. Any E2E failure propagates
#      OVERALL_RC=1 so CI gates read the difference.
#
# The existing first loop (cases.csv smoke) is byte-identical above —
# this block lives AFTER its [SUMMARY] line and uses different
# variable names (E2E_*) to avoid collision.
# ---------------------------------------------------------------------------
E2E_RC=0
if [ -n "${CASES_CSV_E2E:-}" ]; then
    if [ ! -r "$CASES_CSV_E2E" ]; then
        printf '[FAIL] CASES_CSV_E2E=%s not readable\n' "$CASES_CSV_E2E" >&2
        E2E_RC=1
    else
        E2E_PARSED="$(mktemp)"
        E2E_PARSE_ERR="$(mktemp)"
        if ! parse_csv "$CASES_CSV_E2E" > "$E2E_PARSED" 2> "$E2E_PARSE_ERR"; then
            cat "$E2E_PARSE_ERR" >&2
            if ! python3 "$SCRIPT_DIR/_dump_parse_trace.py" "$LOGS_DIR" "$E2E_PARSE_ERR" 2>/dev/null; then
                printf '[WARN] could not write parse-fail trace to %s\n' "$LOGS_DIR" >&2
            fi
            printf '[FAIL] %s rejected by parse_csv — see [PARSE-FAIL] above\n' "$CASES_CSV_E2E" >&2
            rm -f "$E2E_PARSED" "$E2E_PARSE_ERR"
            E2E_RC=1
        else
            rm -f "$E2E_PARSE_ERR"
            E2E_TOTAL=$(tr -cd '\0' < "$E2E_PARSED" | wc -c | tr -d '[:space:]')
            E2E_PASSED=0
            E2E_FAILED=0
            E2E_ROW=0

            # Read the four fields per record (prompt + 3 counts). We
            # ignore the count columns; the E2E loop's contract is
            # routing-shape (not counts) so they stay at baseline 0,0,0.
            while IFS=$'\t' read -r -d '' E2E_PROMPT E2E_EXP_TOOLS E2E_EXP_SKILLS E2E_EXP_SUBAGENTS; do
                E2E_ROW=$((E2E_ROW + 1))
                E2E_SLUG=$(slugify "$E2E_PROMPT")

                trace_text=$(run_row "$E2E_ROW" "$E2E_PROMPT" || true)
                [ -z "$trace_text" ] && trace_text=""

                # ALWAYS dump the trace (RED surface) — same filename
                # shape as the smoke loop's dump_failure_trace so RED
                # traces share the directory convention.
                E2E_TRACE_FILE="${LOGS_DIR}/${E2E_ROW}-${E2E_SLUG}.json"
                E2E_TRACE_FILE=$(printf '%s' "$E2E_TRACE_FILE" | tr -c 'A-Za-z0-9._-' '-')
                [ "${#E2E_TRACE_FILE}" -gt 64 ] && E2E_TRACE_FILE="${E2E_TRACE_FILE:0:64}"
                printf '%s' "$trace_text" > "$E2E_TRACE_FILE"

                # Per-fixture routing decision via _e2e_runner.py.
                # stdout -> /dev/null (verdict is the exit code); stderr
                # -> surface (so REASON lines from a failing row reach
                # the host harness via 2>&1).
                e2e_row_rc=0
                if ! python3 "$SCRIPT_DIR/_e2e_runner.py" \
                        "$E2E_SLUG" "$E2E_TRACE_FILE" >/dev/null; then
                    e2e_row_rc=1
                fi

                if [ "$e2e_row_rc" -eq 0 ]; then
                    printf '[E2E-ASSERT] fixture=%s row=%d pass\n' \
                        "$E2E_SLUG" "$E2E_ROW"
                    E2E_PASSED=$((E2E_PASSED + 1))
                else
                    printf '[E2E-ASSERT] fixture=%s row=%d fail\n' \
                        "$E2E_SLUG" "$E2E_ROW"
                    E2E_FAILED=$((E2E_FAILED + 1))
                    E2E_RC=1
                fi
            done < "$E2E_PARSED"

            rm -f "$E2E_PARSED"

            printf '[E2E-SUMMARY] passed=%d failed=%d total=%d\n' \
                "$E2E_PASSED" "$E2E_FAILED" "$E2E_TOTAL" >&2
        fi
    fi
fi

# E2E failures bump OVERALL_RC so the existing smoke-pass result does
# not mask a RED regression. CI gates read the aggregate exit code.
if [ "$E2E_RC" -ne 0 ]; then
    OVERALL_RC=1
fi

exit "$OVERALL_RC"