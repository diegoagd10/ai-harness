#!/usr/bin/env python3
"""cases_csv.test.py — verifies tests-prompts/cases.csv after the
fix-cases-csv-encoding task.

Subtasks covered:
  5.1  Row 2 prompt quoted; csv.DictReader sees single field
       'hello, how are you doing?'.
  5.2  Row 4 prompt quoted; csv.DictReader sees single field
       'Hola!!, como estas?'.
  5.3  Counts on rows 2 and 4 remain 0,0,0 (no invented values).
  5.4  Row 5 interpretation selected (B), recorded in this CSV's
       header comment + the commit message. Tests below verify
       the chosen form (short prompt, counts 0,0,0).
  5.5  Header (covered by tests/compare_count.test.sh).
  Plus: parse_csv.py skips '#' comment lines so cases.csv can carry
  self-documentation. Confirmed by an integration check below.
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
import unittest

SCRIPT_DIR = os.path.dirname(__file__)
CASES_CSV = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "cases.csv"))
PARSER_PY = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "parse_csv.py"))


def _read_csv_lines_skipping_comments(path: str) -> list[str]:
    """Mirror parse_csv.py: lines starting with '#' are skipped."""
    with open(path, "r", encoding="utf-8") as f:
        return [line for line in f if not line.lstrip().startswith("#")]


class TestCasesCsvStructure(unittest.TestCase):
    """5.1 / 5.2 / 5.3 / 5.4 — cases.csv shape after the data fix."""

    def setUp(self):
        if not os.path.isfile(CASES_CSV):
            self.skipTest(f"cases.csv not found at {CASES_CSV}")
        # Mirror parse_csv.py: skip comment lines.
        self.raw_lines = _read_csv_lines_skipping_comments(CASES_CSV)
        with open(CASES_CSV, "r", encoding="utf-8", newline="") as f:
            non_comment = (line for line in f if not line.lstrip().startswith("#"))
            in_memory = io.StringIO("".join(non_comment))
            reader = csv.DictReader(in_memory)
            self.rows = list(reader)

    def test_file_has_five_data_rows(self):
        """Sanity — 5 data rows after the fix (rows 1, 2, 3, 4, 5)."""
        self.assertEqual(
            len(self.rows),
            5,
            msg=f"expected 5 data rows, got {len(self.rows)}: {self.rows!r}",
        )

    def test_row_2_prompt_is_single_quoted_field(self):
        """5.1 — Row 2 prompt is one field: 'hello, how are you doing?'."""
        # raw_lines[0] is header, so data starts at index 1.
        # But because parse_csv and DictReader skip comments, raw_lines
        # already excludes them. Confirm directly via the parsed data:
        row = self.rows[1]  # row 2 (1-based), data[1] (0-based after header)
        self.assertEqual(row.get("prompt"), "hello, how are you doing?")
        self.assertEqual(row.get(" tools calls (number)"), "0")
        self.assertEqual(row.get(" skills calls (number)"), "0")
        self.assertEqual(row.get(" sub-agent calls (number)"), "0")
        self.assertIsNone(
            row.get(None),
            "row.get(None) must be None (no trailing-field shift)",
        )

    def test_row_4_prompt_is_single_quoted_field(self):
        """5.2 — Row 4 prompt is one field: 'Hola!!, como estas?'."""
        row = self.rows[3]  # row 4 (1-based)
        self.assertEqual(row.get("prompt"), "Hola!!, como estas?")
        self.assertEqual(row.get(" tools calls (number)"), "0")
        self.assertEqual(row.get(" skills calls (number)"), "0")
        self.assertEqual(row.get(" sub-agent calls (number)"), "0")
        self.assertIsNone(row.get(None))

    def test_row_2_counts_remain_zero(self):
        """5.3 — Row 2 trailing columns remain 0,0,0 (no invented values)."""
        # The raw line for row 2 must end with ',0,0,0' — the fix is
        # quoting only; counts are unchanged.
        row2 = None
        for raw_line in self.raw_lines:
            if raw_line.startswith('"hello, how are you doing?"'):
                row2 = raw_line
                break
        self.assertIsNotNone(row2, "row 2 (quoted) not found in source")
        # Strip the trailing newline before checking suffix.
        self.assertTrue(
            row2.rstrip("\n").endswith(",0,0,0"),
            msg=f"row 2 must end with ',0,0,0', got: {row2!r}",
        )

    def test_row_4_counts_remain_zero(self):
        """5.3 — Row 4 trailing columns remain 0,0,0."""
        row4 = None
        for raw_line in self.raw_lines:
            if raw_line.startswith('"Hola!!, como estas?"'):
                row4 = raw_line
                break
        self.assertIsNotNone(row4, "row 4 (quoted) not found in source")
        self.assertTrue(
            row4.rstrip("\n").endswith(",0,0,0"),
            msg=f"row 4 must end with ',0,0,0', got: {row4!r}",
        )

    def test_row_5_short_prompt_interpretation_b(self):
        """5.4 — Row 5 chosen interpretation B: short prompt, counts 0,0,0.

        Interpretation B treats the original ',10,0,0' as junk and
        sets both the prompt back to 'Create a simple python script
        for fibonacci' and the counts to 0,0,0. This is the
        user-default per the user's instruction ('user-default
        interpretation'); the choice is documented in the CSV header
        comment AND in the commit message AND in this test.
        """
        row = self.rows[4]  # row 5 (1-based)
        self.assertEqual(
            row.get("prompt"),
            "Create a simple python script for fibonacci",
        )
        self.assertEqual(row.get(" tools calls (number)"), "0")
        self.assertEqual(row.get(" skills calls (number)"), "0")
        self.assertEqual(row.get(" sub-agent calls (number)"), "0")

    def test_csv_carries_self_documentation_in_comment_lines(self):
        """cases.csv self-documents the row 5 interpretation in a # comment.

        The implementation record: per the user's instruction
        ('document selected interpretation, do not silently resolve
        without traceability'), the row-5 decision is recorded in
        this file's leading # block AND in the commit message.
        """
        with open(CASES_CSV, "r", encoding="utf-8") as f:
            raw = f.read()
        # The CSV carries a non-empty, recognizable interpretation note.
        self.assertIn("#", raw, "cases.csv must contain at least one # line")
        self.assertIn(
            "interpretation",
            raw.lower(),
            msg="cases.csv must document the row-5 interpretation in a # line",
        )
        # The exact row-5 reference must be present.
        self.assertIn("Row 5", raw)


class TestParserAcceptsFixedCsv(unittest.TestCase):
    """parse_csv.py must accept the fixed cases.csv.

    With the data fix in place:
      - parse_csv exits 0
      - stdout contains 5 NUL-terminated records
      - stderr is empty (no [PARSE-FAIL]).
    """

    def setUp(self):
        if not os.path.isfile(PARSER_PY):
            self.skipTest(f"parse_csv.py not found at {PARSER_PY}")
        if not os.path.isfile(CASES_CSV):
            self.skipTest(f"cases.csv not found at {CASES_CSV}")

    def test_cli_accepts_fixed_cases_csv(self):
        result = subprocess.run(
            [sys.executable, PARSER_PY, CASES_CSV],
            capture_output=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"parser must accept the fixed CSV; stderr={result.stderr!r}",
        )
        # 5 records → 5 NUL bytes in stdout.
        self.assertEqual(
            result.stdout.count(b"\0"),
            5,
            msg=f"expected 5 NUL-terminated records, got stdout={result.stdout!r}",
        )
        # Parse the records for spot checks on row 2 and row 4 prompts.
        records = result.stdout.split(b"\0")[:-1]  # drop trailing empty
        self.assertEqual(len(records), 5)
        prompts = [r.split(b"\t")[0].decode("utf-8") for r in records]
        self.assertIn("hello", prompts)
        self.assertIn("hello, how are you doing?", prompts)
        self.assertIn("Hola", prompts)
        self.assertIn("Hola!!, como estas?", prompts)
        self.assertIn("Create a simple python script for fibonacci", prompts)
        # Stderr must NOT contain [PARSE-FAIL] on a fixed CSV.
        self.assertNotIn(b"[PARSE-FAIL]", result.stderr)


class TestParserHandlesMalformedFixture(unittest.TestCase):
    """parse_csv.py still rejects malformed CSVs (task 2 contract held).

    Independent of cases.csv — uses a fixture with an unquoted comma in
    the prompt. Confirms that the parser hardening (and the comment-
    skipping logic added in this task) cooperate correctly: a CSV that
    has both # comments AND a malformed row must surface the row-2
    error without confusion.
    """

    def setUp(self):
        if not os.path.isfile(PARSER_PY):
            self.skipTest(f"parse_csv.py not found at {PARSER_PY}")

    def test_cli_rejects_malformed_row_with_comments_present(self):
        import tempfile

        # Header row + one well-formed row + one malformed data row →
        # the malformed row is data row 2 → "row 2" in the [PARSE-FAIL].
        bad_csv = (
            "# leading comment\n"
            "prompt, tools calls (number), skills calls (number), "
            "sub-agent calls (number)\n"
            "good,0,0,0\n"
            "hello, how are you doing?,0,0,0\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
            f.write(bad_csv)
            path = f.name
        try:
            result = subprocess.run(
                [sys.executable, PARSER_PY, path],
                capture_output=True,
            )
            self.assertNotEqual(
                result.returncode,
                0,
                msg=f"parser must reject; stderr={result.stderr!r}",
            )
            self.assertEqual(
                result.stdout,
                b"",
                msg=f"stdout must be empty on parse failure; got: {result.stdout!r}",
            )
            stderr = result.stderr.decode("utf-8", errors="replace")
            self.assertIn("[PARSE-FAIL]", stderr)
            self.assertIn("row 2", stderr)  # the malformed data row
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
