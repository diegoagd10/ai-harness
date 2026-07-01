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

# parse_csv <path> — streams CSV rows as TAB-fielded, NUL-terminated records
# on stdout. One record per non-blank data row:
#   <prompt>\t<tools>\t<skills>\t<subs>\0
# Delegates to tests-prompts/parse_csv.py (the validate-csv-row-shape seam)
# which owns row-shape correctness: trailing-field shifts, non-integer
# counts, empty prompts all produce a labeled [PARSE-FAIL] line on stderr
# and a non-zero exit. The original bug was a heredoc that quietly
# `or "0"` defaulted missing cells — the seam exists so that class of
# failure can't reach the per-row loop.
parse_csv() {
    local path="$1"
    python3 "$SCRIPT_DIR/parse_csv.py" "$path"
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
# This works for both single-line and multiline prompts because the
# bridge uses NUL as its sole record terminator.
TOTAL=$(parse_csv "$CASES_CSV" | tr -cd '\0' | wc -c | tr -d '[:space:]')
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
done < <(parse_csv "$CASES_CSV")

printf '[SUMMARY] passed=%d failed=%d total=%d\n' "$PASSED" "$FAILED" "$TOTAL" >&2
exit "$OVERALL_RC"