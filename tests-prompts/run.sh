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
#   - extract_counts       (tests-prompts/_extractor.py) — schema lives
#                           HERE ONLY; everything else consumes the
#                           returned triple.
#   - slugify              (inline) — fs-safe prompt prefix
#   - dump_failure_trace   (inline) — writes failure-only /logs/<row>-<slug>.json
#   - run_row              (inline) — per-row opencode invocation adapter
set -uo pipefail

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
# Uses Python csv.DictReader so commas/newlines/quotes in prompts work.
# NUL is the record separator (bash `read -d ''` consumes one record at a
# time) so prompts with embedded newlines survive intact.
parse_csv() {
    local path="$1"
    python3 - "$path" <<'PYEOF'
import csv
import sys

path = sys.argv[1]
with open(path, newline="") as f:
    reader = csv.DictReader(f)
    field_tools = " tools calls (number)"
    field_skills = " skills calls (number)"
    field_subs = " sub-agent calls (number)"
    for row in reader:
        prompt = (row.get("prompt") or "").strip()
        if not prompt:
            continue
        tools = (row.get(field_tools) or "0").strip() or "0"
        skills = (row.get(field_skills) or "0").strip() or "0"
        subs = (row.get(field_subs) or "0").strip() or "0"
        # TAB between fields, NUL between records. No trailing newline:
        # the NUL is the only record terminator, so prompts with embedded
        # newlines are not mistaken for record boundaries by `read -d ''`.
        sys.stdout.buffer.write(
            f"{prompt}\t{tools}\t{skills}\t{subs}\0".encode("utf-8")
        )
PYEOF
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
    if [ "$got_tools" -ne "$exp_tools" ]; then
        printf '[FAIL] row %d (%s): tools calls expected %s got %s\n' \
            "$ROW_INDEX" "$PROMPT" "$exp_tools" "$got_tools" >&2
        row_rc=1
    fi
    if [ "$got_skills" -ne "$exp_skills" ]; then
        printf '[FAIL] row %d (%s): skills calls expected %s got %s\n' \
            "$ROW_INDEX" "$PROMPT" "$exp_skills" "$got_skills" >&2
        row_rc=1
    fi
    if [ "$got_subs" -ne "$exp_subs" ]; then
        printf '[FAIL] row %d (%s): sub-agent calls expected %s got %s\n' \
            "$ROW_INDEX" "$PROMPT" "$exp_subs" "$got_subs" >&2
        row_rc=1
    fi

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