#!/usr/bin/env python3
"""parse_csv.py — row-shape-aware CSV reader for tests-prompts/cases.csv.

This module is the single seam that owns row-shape correctness for the
prompt-test runner. Replacing it with inline shell + Python heredoc is
how the original bug landed in the first place. Keep it tight; keep it
testable; do not let run.sh grow validation logic back into shell.

CLI
---
    python3 parse_csv.py <path>

        On stdout: TAB-fielded, NUL-terminated records — one record per
        data row, shape `<prompt>\\t<tools>\\t<skills>\\t<subs>\\0`.
        The NUL is the record terminator (so embedded newlines survive
        through `read -d ''`); TAB is the field separator inside a record.

        On a row-shape error (wrong column count, non-integer count
        field, empty prompt): writes a labeled
            `[PARSE-FAIL] row N (prompt-prefix): <reason> — got <value>`
        line to stderr and exits 1.

Python API
----------
    parse_rows(path) -> Iterator[Row]

        where Row = (prompt: str, tools: int, skills: int, subs: int).

        Fails fast on the first malformed row by raising CsvShapeError
        whose attributes are:
            - row_index (1-based; row 1 is the first data row)
            - reason (human-readable, names the failing column)
            - offending_value (the literal value that triggered the error)

Header field names are matched exactly as written in cases.csv — the
leading spaces in ` tools calls (number)` etc. are part of the header
and are preserved as DictReader keys. Trailing-field shift (the original
bug) is caught via `row.get(None) is not None`.

Runs on the host without Docker, the orchestrator, or any model. Stays
small so the next contributor can hold it in their head.
"""

from __future__ import annotations

import csv
import io
import sys
from typing import Iterator

# Header field names — leading spaces are part of the header in cases.csv.
FIELD_PROMPT = "prompt"
FIELD_TOOLS = " tools calls (number)"
FIELD_SKILLS = " skills calls (number)"
FIELD_SUBS = " sub-agent calls (number)"

COUNT_FIELDS: tuple[str, str, str] = (FIELD_TOOLS, FIELD_SKILLS, FIELD_SUBS)

# Maximum bytes of the original prompt kept in CLI error prefixes. Long
# enough to identify the row, short enough to keep stderr lines readable.
PROMPT_PREFIX_LIMIT = 32


class CsvShapeError(Exception):
    """Raised on the first malformed row.

    Attributes:
        row_index: 1-based row index (1 = first data row).
        reason: human-readable explanation naming the failing column.
        offending_value: the literal value that triggered the failure.
    """

    def __init__(self, row_index: int, reason: str, offending_value):
        self.row_index = row_index
        self.reason = reason
        self.offending_value = offending_value
        super().__init__(f"row {row_index}: {reason} — got {offending_value!r}")


def _prompt_prefix(prompt) -> str:
    """Single-line, length-capped prompt prefix for CLI error lines."""
    text = (prompt or "").replace("\n", "\\n").replace("\t", "\\t")
    if len(text) > PROMPT_PREFIX_LIMIT:
        text = text[:PROMPT_PREFIX_LIMIT]
    return text or "(empty)"


def _is_non_negative_int(value: str) -> bool:
    """True iff value matches ^[0-9]+$ (after this function's stripping)."""
    if not value:
        return False
    return all(c in "0123456789" for c in value)


def _coerce_row(row: dict, row_index: int) -> tuple[str, int, int, int]:
    """Validate a DictReader row; return Row on success.

    Raises CsvShapeError on the first issue. The checks run in order:
      1) trailing-field shift  (extra columns under row.get(None))
      2) empty prompt          (after .strip())
      3) any count column not a non-negative integer
    """
    # 1) Trailing-field shift: csv.DictReader dumps extra columns under None.
    extra = row.get(None)
    if extra is not None:
        raw_prompt = row.get(FIELD_PROMPT) or ""
        raise CsvShapeError(
            row_index,
            "trailing-field shift (extra columns beyond header)",
            repr(extra),
        )

    # 2) Prompt: non-empty after stripping.
    raw_prompt = row.get(FIELD_PROMPT) or ""
    prompt = raw_prompt.strip()
    if not prompt:
        raise CsvShapeError(row_index, "prompt is empty", raw_prompt)

    # 3) Each count column: ^[0-9]+$ after stripping.
    counts = []
    for field in COUNT_FIELDS:
        raw = (row.get(field) or "").strip()
        if not _is_non_negative_int(raw):
            raise CsvShapeError(
                row_index,
                f"{field.strip()} not a non-negative integer",
                raw,
            )
        counts.append(int(raw))

    return (prompt, counts[0], counts[1], counts[2])


def parse_rows(path: str) -> Iterator[tuple[str, int, int, int]]:
    """Yield (prompt, tools, skills, subs) tuples from `path`.

    Fails fast on the first malformed row by raising CsvShapeError.
    A row whose prompt cell is empty is treated as malformed (the
    original parser silently skipped such rows; we refuse that).

    Lines starting with `#` (after optional leading whitespace) are
    skipped so the CSV file can carry inline documentation (e.g. a
    TODO marker for an unresolved user-intent ambiguity on a row).
    The line-number reported in CsvShapeError is the row_index of the
    CSV data row — comments do not count toward that index.
    """
    with open(path, "r", encoding="utf-8") as fh:
        non_comment = (line for line in fh if not line.lstrip().startswith("#"))
        in_memory = io.StringIO("".join(non_comment))
        reader = csv.DictReader(in_memory)
        for row_index, row in enumerate(reader, start=1):
            yield _coerce_row(row, row_index)


def _emit_cli_error_with_prefix(row_index: int, reason: str, offending_value, prefix_hint: str) -> None:
    """Write the labeled [PARSE-FAIL] line on stderr.

    `prefix_hint` is the unstripped prompt text for the row (used in the
    error so a human can locate the offending row by reading stderr).
    """
    prefix = _prompt_prefix(prefix_hint)
    sys.stderr.write(f"[PARSE-FAIL] row {row_index} ({prefix}): {reason} — got {offending_value!r}\n")


def _cli_main(path: str) -> int:
    """Drive the CSV reader from the CLI path. Returns process exit code.

    Two-pass design: validate every row first, emit only after the whole
    file passes. Rationale: if a downstream consumer sees partial stdout,
    they cannot tell whether the failure occurred before or after the
    emitted bytes — the contract is "all or nothing."
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            non_comment = (line for line in fh if not line.lstrip().startswith("#"))
            in_memory = io.StringIO("".join(non_comment))
            reader = csv.DictReader(in_memory)
            validated: list[tuple[str, int, int, int]] = []
            for row_index, row in enumerate(reader, start=1):
                raw_prompt = row.get(FIELD_PROMPT) or ""
                try:
                    validated.append(_coerce_row(row, row_index))
                except CsvShapeError as exc:
                    _emit_cli_error_with_prefix(row_index, exc.reason, exc.offending_value, raw_prompt)
                    return 1
    except FileNotFoundError:
        sys.stderr.write(f"[PARSE-FAIL] file not found: {path}\n")
        return 1

    for prompt, tools, skills, subs in validated:
        sys.stdout.buffer.write(f"{prompt}\t{tools}\t{skills}\t{subs}\0".encode("utf-8"))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        sys.stderr.write("usage: parse_csv.py <path>\n")
        return 2
    return _cli_main(argv[0])


if __name__ == "__main__":
    sys.exit(main())
