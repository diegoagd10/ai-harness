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
# Internal helpers (defined inline further down):
#   - extract_counts       — only place that knows opencode JSON schema
#   - dump_failure_trace   — writes failure-only /logs/<row>-<slug>.json
#   - slugify              — fs-safe prompt prefix for trace filenames
#   - run_row              — per-row opencode invocation adapter
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
# Per-row loop — expanded by tasks 5/6 (placeholder for now).
# ---------------------------------------------------------------------------
printf '[INFO] bootstrap OK — per-row loop not yet implemented\n' >&2
exit 0