#!/usr/bin/env python3
"""_dump_parse_trace.py — emit a structured JSON trace under $LOGS_DIR
on parse_csv.py rejection.

Validator finding that drove this slice:
    parse-time CSV failures do not write the required structured
    artifact into $LOGS_DIR / dump_failure_trace-equivalent output.

PRD contract (prd.md "Surface the fix in the row's failure trace"):
    When a row is rejected by parse_csv, write a structured entry
    to $LOGS_DIR (same shape as dump_failure_trace) so CI scrapers
    and humans see the same artifact regardless of where the
    failure originates.

This helper closes the row-rejection → logs-directory gap. It lives
next to `_extractor.py` because the parser and the trace-dumper have
different responsibilities:

    parse_csv.py        — owns row-shape correctness, emits labeled
                          [PARSE-FAIL] on stderr
    _dump_parse_trace.py — owns "translate that labeled stderr into a
                            $LOGS_DIR/<row>-<slug>.json artifact
                            that CI can scrape"

The two together make per-row PASS/FAIL (`dump_failure_trace`) and
parse-fail (`_dump_parse_trace`) both surface in the same logs
directory with the same artifact semantics.

CLI
---
    python3 _dump_parse_trace.py <LOGS_DIR> <STDERR_FILE>

        STDERR_FILE is the captured stderr from a parse_csv.py
        invocation that exited non-zero. The first line matching
        the regex `\\[PARSE-FAIL\\] row (\\d+)` determines the
        row_index for the artifact basename. The full stderr text
        is preserved verbatim in the JSON document.

        On success: writes $LOGS_DIR/parse-fail-<row_index>.json
        containing
            {
              "source": "parse_csv",
              "row_index": <int>,
              "stderr": "<verbatim captured stderr>"
            }

        On signals (no parse-fail in stderr, or empty file):
        writes NO artifact and exits 0 — run.sh will continue with
        its own exit-1 path. The helper never fabricates a
        parse-fail artifact from non-parse-fail input.

        On usage errors (missing args, missing file): writes a
        usage line to stderr and exits 2. run.sh can `|| true`
        this and continue.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Stable, narrow regex — only the parse_csv.py contract shape. If the
# parser's stderr contract ever changes, this fails closed (no
# artifact) which is the conservative behavior for a CI scraper.
PARSE_FAIL_RE = re.compile(r"\[PARSE-FAIL\] row (\d+)")


def _emit_trace(logs_dir: str, stderr_text: str) -> int:
    """Parse stderr for the [PARSE-FAIL] row index and write the trace.

    Returns 0 when an artifact was written OR when there was no
    parse-fail signal (write nothing); returns 2 on hard usage errors.
    Caller decides whether non-zero is fatal.
    """
    match = PARSE_FAIL_RE.search(stderr_text)
    if match is None:
        # No parse-fail signal: nothing to do. run.sh still has the
        # stderr in $parse_err and continues to its own exit-1 path.
        return 0

    row_index = int(match.group(1))
    document = {
        "source": "parse_csv",
        "row_index": row_index,
        "stderr": stderr_text,
    }
    out_path = Path(logs_dir) / f"parse-fail-{row_index}.json"
    # Hard 64-char cap on the basename (matches dump_failure_trace's
    # cap in run.sh) — defensive against a hypothetical future
    # parse_csv.py that emits a giant row index.
    if len(out_path.name) > 64:
        out_path = out_path.with_name(out_path.name[:64])
    out_path.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        sys.stderr.write("usage: _dump_parse_trace.py <LOGS_DIR> <STDERR_FILE>\n")
        return 2
    logs_dir = argv[0]
    stderr_path = argv[1]
    if not os.path.isdir(logs_dir):
        sys.stderr.write(f"[WARN] logs dir not found: {logs_dir}\n")
        return 2
    if not os.path.isfile(stderr_path):
        sys.stderr.write(f"[WARN] stderr file not found: {stderr_path}\n")
        return 2
    stderr_text = Path(stderr_path).read_text(encoding="utf-8", errors="replace")
    return _emit_trace(logs_dir, stderr_text)


if __name__ == "__main__":
    sys.exit(main())
