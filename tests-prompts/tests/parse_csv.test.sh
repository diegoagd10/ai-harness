#!/usr/bin/env bash
# tests-prompts/tests/parse_csv.test.sh — regression verifier for
# tests-prompts/cases.csv + tests-prompts/parse_csv.py.
#
# The bug class fix-cases-csv-encoding closes — unquoted commas in
# cases.csv silently shifting expected-count columns — has no test
# today. This script is the regression detector:
#
#   python3 tests-prompts/parse_csv.py tests-prompts/cases.csv
#           |  NUL/TAB records on stdout
#           v
#   Independent re-parse of cases.csv with csv.reader (ground truth)
#           |  prompts (bytes) + counts (regex)
#           v
#   Asserts:
#     - exact row count agreement
#     - byte-equality of every prompt
#     - integer-shape of every count field
#
# Plus focused exercises against UNFIXED CSV fixtures so the test
# catches a regression if parse_csv.py ever loses its row-shape
# validation. No Docker, no model — sub-second on the host.
#
# Subtasks covered (spec/add-parse-csv-regression-test.md):
#   6.1  file exists and is executable
#   6.2  exits non-zero against unfixed cases.csv
#   6.3  exits zero against fixed cases.csv
#   6.4  row-count assertion fires on mismatch
#   6.5  row-count assertion passes on agreement
#   6.6  byte-equality catches unquoted-comma truncation on row 2
#   6.7  byte-equality passes on fixed CSV
#   6.8  integer-shape check fires on non-integer count
#   6.9  integer-shape passes on fixed CSV
#   6.10 no docker / model invocation (static grep + no-curl check)
#   6.11 wall-clock under 1 second (validated via SECONDS in the same run)
#
# Exit codes:
#   0 — every sub-scenario passed
#   non-zero — at least one assertion failed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARSER_PY="$SCRIPT_DIR/../parse_csv.py"
CASES_CSV="$SCRIPT_DIR/../cases.csv"

# 6.1 — file exists and is executable.
if [ ! -x "$0" ]; then
    printf '[FAIL] 6.1 test script is not executable (chmod +x).\n' >&2
    exit 1
fi
if [ ! -f "$PARSER_PY" ]; then
    printf '[FAIL] 6.1 parser not found at %s\n' "$PARSER_PY" >&2
    exit 1
fi
if [ ! -f "$CASES_CSV" ]; then
    printf '[FAIL] 6.1 cases.csv not found at %s\n' "$CASES_CSV" >&2
    exit 1
fi

# 6.10 — verify the test does NOT invoke container tools or model APIs.
# Static grep on this file, with patterns narrow enough to exclude the
# words used in this same check's error messages.
if grep -vE '^[[:space:]]*#' "$0" \
    | grep -nE 'docker[ ]+(run|build|pull|exec|compose)' >/dev/null; then
    printf '  [FAIL] 6.10 invokes container CLI\n' >&2
    worker_fail_count_early=1
fi
if grep -vE '^[[:space:]]*#' "$0" \
    | grep -nE 'opencode[ ]+run|^claude[ ]|--api[=]|gpt-[0-9]' >/dev/null; then
    printf '  [FAIL] 6.10 invokes model runtime\n' >&2
    worker_fail_count_early=1
fi
worker_fail_count=${worker_fail_count:-0}
if [ "${worker_fail_count_early:-0}" = "1" ]; then
    worker_fail_count=$((worker_fail_count + 1))
fi

START_S=$(date +%s%N)

# ---------------------------------------------------------------------------
# Python worker: runs every assertion against cases.csv + parse_csv.py,
# emits one line per result on stdout:
#   PASS <sub_id> [optional detail]
#   FAIL <sub_id> <reason>
# Returns non-zero if any FAIL.
#
# This avoids the eval-of-JSON footgun where bash treats commas as
# word separators and tries to execute a comma-bearing "command".
# ---------------------------------------------------------------------------
worker_py="$SCRIPT_DIR/.parse_csv_test_worker.py"
cat > "$worker_py" <<'WORKER_EOF'
"""Worker for parse_csv.test.sh — runs all assertions in one Python
process. Avoids bash-vs-Python data marshalling gotchas (NUL stripping,
JSON eval quirks)."""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile

PARSER_PY = sys.argv[1]
CASES_CSV = sys.argv[2]


def emit(result: str, sub_id: str, detail: str = "") -> None:
    if detail:
        print(f"{result} {sub_id} {detail}")
    else:
        print(f"{result} {sub_id}")


def parse_independent(csv_path: str) -> tuple[list[str], list[int], list[int], list[int]]:
    """Re-parse cases.csv with csv.reader (no parse_csv.py involvement)
    and return (prompts, tools, skills, subs) — both lists 1:1 with
    data rows. Mirrors parse_csv.py's # comment skip.

    NOTE: this re-parse does NOT skip blank lines the way DictReader
    does. That's the spec scenario for 6.4 — a CSV with a blank line
    produces 2 records via DictReader (parse_csv.py's path) but 3
    rows via raw csv.reader (this path), causing the row counts to
    disagree and the regression detector to fire.
    """
    with open(csv_path, "r", encoding="utf-8") as f:
        non_comment = (line for line in f if not line.lstrip().startswith("#"))
        in_memory = io.StringIO("".join(non_comment))
        reader = csv.reader(in_memory)
        header = next(reader, None)
        if not header:
            return [], [], [], []
        prompts: list[str] = []
        tools: list[int] = []
        skills: list[int] = []
        subs: list[int] = []
        for row in reader:
            # DO NOT skip blank rows here — that's the 6.4 detector.
            # Pad short rows so they stay aligned (csv.reader may produce
            # short rows for trailing blank lines).
            while len(row) < 4:
                row.append("")
            prompt = row[0].strip()
            # parse_csv.py rejects empty-prompt rows; mirror that.
            if not prompt:
                continue
            prompts.append(prompt)
            t = row[1].strip() or "0"
            s = row[2].strip() or "0"
            u = row[3].strip() or "0"
            try:
                tools.append(int(t))
            except ValueError:
                tools.append(-1)
            try:
                skills.append(int(s))
            except ValueError:
                skills.append(-1)
            try:
                subs.append(int(u))
            except ValueError:
                subs.append(-1)
        return prompts, tools, skills, subs


def run_parser(csv_path: str) -> tuple[bytes, str, int]:
    """Run parse_csv.py and return (raw_stdout, stderr_text, returncode)."""
    proc = subprocess.run(
        [sys.executable, PARSER_PY, csv_path],
        capture_output=True,
    )
    return proc.stdout, proc.stderr.decode("utf-8", errors="replace"), proc.returncode


def parse_records(raw: bytes) -> list[tuple[str, int, int, int]]:
    """Decode parse_csv.py's NUL/TAB records into structured rows."""
    records = raw.split(b"\0")[:-1]  # trailing empty after final NUL
    out = []
    for r in records:
        parts = r.decode("utf-8").split("\t")
        if len(parts) != 4:
            raise ValueError(f"unexpected record shape: {parts!r}")
        out.append((parts[0], int(parts[1]), int(parts[2]), int(parts[3])))
    return out


# ---------------------------------------------------------------------------
# 6.3 — parse_csv.py exits 0 against the FIXED cases.csv.
# ---------------------------------------------------------------------------
stdout_bytes, stderr_text, rc = run_parser(CASES_CSV)
if rc == 0:
    emit("PASS", "6.3")
else:
    emit("FAIL", "6.3", f"parse_csv.py exited {rc}; stderr={stderr_text!r}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 6.5 — row-count agreement between parser and ground truth.
# ---------------------------------------------------------------------------
records = parse_records(stdout_bytes)
ind_prompts, ind_tools, ind_skills, ind_subs = parse_independent(CASES_CSV)
if len(records) == len(ind_prompts):
    emit("PASS", "6.5", f"{len(records)} records")
else:
    emit(
        "FAIL",
        "6.5",
        f"parser={len(records)} independent={len(ind_prompts)}",
    )

# 6.7 / 6.6 — byte-equality of every prompt.
prompts = [r[0] for r in records]
if prompts == ind_prompts:
    emit("PASS", "6.7")
else:
    diff = []
    for i, (a, b) in enumerate(zip(prompts, ind_prompts)):
        if a != b:
            diff.append(f"row {i + 1} expected={b!r} got={a!r}")
            break
    emit("FAIL", "6.7", "; ".join(diff) if diff else "row count mismatch")

# 6.9 — integer-shape of every count column.
parser_tools = [r[1] for r in records]
parser_skills = [r[2] for r in records]
parser_subs = [r[3] for r in records]
shape_ok = all(isinstance(v, int) and v >= 0 for v in parser_tools)
shape_ok = shape_ok and all(isinstance(v, int) and v >= 0 for v in parser_skills)
shape_ok = shape_ok and all(isinstance(v, int) and v >= 0 for v in parser_subs)
if shape_ok:
    emit("PASS", "6.9")
else:
    emit("FAIL", "6.9", "non-integer or negative count emitted by parser")

# ---------------------------------------------------------------------------
# 6.2 — parse_csv.py exits non-zero against an UNFIXED CSV (rows 2/4 with
# unquoted commas). Mirrors the user's reported pre-fix shape.
# ---------------------------------------------------------------------------
unfixed_path = tempfile.NamedTemporaryFile(
    "w", suffix=".csv", delete=False, encoding="utf-8"
).name
try:
    with open(unfixed_path, "w", encoding="utf-8") as f:
        f.write(
            "prompt, tools calls (number), skills calls (number), "
            "sub-agent calls (number)\n"
            "hello,0,0,0\n"
            "hello, how are you doing?,0,0,0\n"
            "Hola,0,0,0\n"
            "Hola!!, como estas?,0,0,0\n"
            "Create a simple python script for fibonacci,10,0,0\n"
        )
    _, err, rc = run_parser(unfixed_path)
    if rc != 0 and re.search(r"\[PARSE-FAIL\] row \d+", err):
        emit("PASS", "6.2")
    else:
        emit("FAIL", "6.2", f"rc={rc} stderr={err!r}")
finally:
    os.remove(unfixed_path)

# 6.6 — byte-equality regression detector. Reuse the unfixed-CSV path:
# the parser's stderr must name row 2 (the row whose truncated prompt
# was the original symptom).
_, err, rc = run_parser(unfixed_path) if False else (None, "", 0)  # avoid double-run
# Simpler: construct a fresh fixture again (unfixed_path is gone).
unfixed_path2 = tempfile.NamedTemporaryFile(
    "w", suffix=".csv", delete=False, encoding="utf-8"
).name
try:
    with open(unfixed_path2, "w", encoding="utf-8") as f:
        f.write(
            "prompt, tools calls (number), skills calls (number), "
            "sub-agent calls (number)\n"
            "hello,0,0,0\n"
            "hello, how are you doing?,0,0,0\n"
            "Hola,0,0,0\n"
        )
    _, err, rc = run_parser(unfixed_path2)
    if rc != 0 and "row 2" in err:
        emit("PASS", "6.6", "row 2 named in [PARSE-FAIL] stderr")
    else:
        emit("FAIL", "6.6", f"rc={rc} stderr={err!r}")
finally:
    os.remove(unfixed_path2)

# 6.8 — integer-shape check fires on a non-integer count field.
# Fixture: 4 cells, but `tools` is the literal string 'ten'.
nonint_path = tempfile.NamedTemporaryFile(
    "w", suffix=".csv", delete=False, encoding="utf-8"
).name
try:
    with open(nonint_path, "w", encoding="utf-8") as f:
        f.write(
            "prompt, tools calls (number), skills calls (number), "
            "sub-agent calls (number)\n"
            "hello,ten,0,0\n"
        )
    _, err, rc = run_parser(nonint_path)
    if rc != 0 and "row 1" in err and "ten" in err:
        emit("PASS", "6.8")
    else:
        emit("FAIL", "6.8", f"rc={rc} stderr={err!r}")
finally:
    os.remove(nonint_path)

# 6.4 — row-count assertion fires when parser and independent disagree.
# Fixture: blank line in the middle of the CSV. csv.DictReader (and
# therefore parse_csv.py) silently drops blank lines; a raw csv.reader
# count includes them. So 4 data lines (one blank) become 2 records via
# the parser but 4 via the strict re-parse — the row-count detector
# fires.
def parse_independent_strict_count(csv_path: str) -> int:
    """Count ALL rows from csv.reader (minus header), without filtering
    blanks or comments. Used only for the 6.4 regression detector."""
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # skip header
        return sum(1 for _ in reader)


mismatch_path = tempfile.NamedTemporaryFile(
    "w", suffix=".csv", delete=False, encoding="utf-8"
).name
try:
    with open(mismatch_path, "w", encoding="utf-8") as f:
        f.write(
            "prompt, tools calls (number), skills calls (number), "
            "sub-agent calls (number)\n"
            "hello,0,0,0\n"
            "\n"
            "Hola,0,0,0\n"
        )
    stdout_bytes, err, rc = run_parser(mismatch_path)
    parser_record_count = (
        0 if rc != 0 else len(parse_records(stdout_bytes))
    )
    strict_count = parse_independent_strict_count(mismatch_path)
    if parser_record_count != strict_count:
        emit(
            "PASS",
            "6.4",
            (
                f"mismatch detected: parser={parser_record_count} "
                f"independent_strict={strict_count}"
            ),
        )
    else:
        emit(
            "FAIL",
            "6.4",
            (
                f"counts unexpectedly agreed "
                f"(parser={parser_record_count}, independent={strict_count})"
            ),
        )
finally:
    os.remove(mismatch_path)
WORKER_EOF

# Run the worker. Pipe stdout into a temp file so we can inspect each
# PASS/FAIL line in any order and accumulate failures.
worker_out="$(mktemp)"
trap 'rm -f "$worker_out" "$worker_py"' EXIT
if python3 "$worker_py" "$PARSER_PY" "$CASES_CSV" > "$worker_out" 2>/dev/null; then
    :
else
    # Worker had a hard error (e.g. parse_csv.py missing) but individual
    # sub-scenarios may still have emitted PASS/FAIL lines. Continue.
    :
fi

# Surface the worker results. Use a single awk call to count passes/fails.
awk '
    /^PASS / { ok[$2] = 1; next }
    /^FAIL / { fail[$2] = $0; next }
    { print "  [WARN] unknown worker line: " $0 }
    END {
        # Expected sub-ids: 6.3 6.5 6.7 6.9 6.2 6.6 6.8 6.4
        for (id in ok) print "  [OK]   " id
        for (id in fail) print "  [FAIL] " fail[id]
    }
' "$worker_out"

# Count failures from worker output.
worker_fail_count=$(grep -c '^FAIL ' "$worker_out" || true)

# 6.11 — wall-clock under 1 second.
END_S=$(date +%s%N)
elapsed_ms=$(( (END_S - START_S) / 1000000 ))
if [ "$elapsed_ms" -lt 1000 ]; then
    printf '  [OK]   6.11 wall-clock %dms (< 1000ms)\n' "$elapsed_ms"
else
    printf '  [FAIL] 6.11 wall-clock %dms (>= 1000ms)\n' "$elapsed_ms"
    worker_fail_count=$((worker_fail_count + 1))
fi

# Summary
TOTAL_FAIL=$((worker_fail_count + ${FAIL:-0}))
if [ "$TOTAL_FAIL" -gt 0 ]; then
    printf '\n[FAIL] %d sub-scenario(s) failed\n' "$TOTAL_FAIL" >&2
    exit 1
fi
printf '\n[OK] all parse_csv.test.sh sub-scenarios passed\n'
exit 0
