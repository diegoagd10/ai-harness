#!/usr/bin/env python3
"""Unit tests for tests-prompts/parse_csv.py.

Covers validate-csv-row-shape spec scenarios:
  2.1 file is on disk and importable
  2.2 CLI emits NUL/TAB records on stdout
  2.3 parse_rows yields tuple iterator for well-formed CSV
  2.4 parse_rows raises CsvShapeError on malformed row
  2.5 CLI catches trailing-field shift
  2.6 CLI catches non-integer count column
  2.7 CLI catches empty prompt
  2.8 CLI fail-fast short-circuits later malformed rows

Runs from the project root or tests-prompts/tests/; resolves the parser
module by relative path so it works regardless of cwd.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

# tests-prompts/tests/parse_csv.test.py -> tests-prompts/parse_csv.py
PARSER_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "parse_csv.py")
)


def _load_module():
    """Import tests-prompts/parse_csv.py by file path."""
    spec = importlib.util.spec_from_file_location("parse_csv_module", PARSER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load spec for {PARSER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_csv(content: str) -> str:
    """Write content to a temp file and return the path (auto-removed)."""
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="parse_csv_test_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


# Header as it appears in tests-prompts/cases.csv (leading spaces preserved).
HEADER = (
    "prompt, tools calls (number), skills calls (number), "
    "sub-agent calls (number)\n"
)


class TestImportable(unittest.TestCase):
    """2.1 — file is on disk and importable."""

    def test_parse_csv_py_exists(self):
        self.assertTrue(
            os.path.isfile(PARSER_PATH),
            f"parse_csv.py must exist at {PARSER_PATH}",
        )

    def test_module_loads_and_exposes_parse_rows(self):
        mod = _load_module()
        self.assertTrue(
            callable(getattr(mod, "parse_rows", None)),
            "parse_rows must be a callable",
        )

    def test_module_exposes_CsvShapeError(self):
        mod = _load_module()
        self.assertTrue(
            hasattr(mod, "CsvShapeError"),
            "parse_csv.py must expose CsvShapeError",
        )


class TestParseRowsApi(unittest.TestCase):
    """2.3 / 2.4 — Python API."""

    def setUp(self):
        self.mod = _load_module()
        self._temp_paths: list[str] = []

    def tearDown(self):
        for path in self._temp_paths:
            try:
                os.remove(path)
            except OSError:
                pass

    def _csv(self, body: str) -> str:
        path = _write_csv(HEADER + body)
        self._temp_paths.append(path)
        return path

    def test_well_formed_csv_yields_tuple_iterator(self):
        """2.3 — well-formed CSV yields tuple iterator."""
        path = self._csv("hello,0,0,0\nHola,0,0,0\n")
        rows = list(self.mod.parse_rows(path))
        self.assertEqual(
            rows,
            [("hello", 0, 0, 0), ("Hola", 0, 0, 0)],
        )

    def test_malformed_row_raises_CsvShapeError(self):
        """2.4 — malformed row raises CsvShapeError with row_index, reason, value."""
        # 5 fields (header has 4) — unquoted comma inside prompt + extra cell.
        # The spec scenario places a well-formed row first, so the malformed
        # row is the second data row → row_index == 2.
        path = self._csv("good,0,0,0\nhello, how are you doing?,0,0,0\n")
        with self.assertRaises(self.mod.CsvShapeError) as ctx:
            list(self.mod.parse_rows(path))
        err = ctx.exception
        self.assertEqual(err.row_index, 2)
        self.assertTrue(err.reason, "reason must be a non-empty string")
        self.assertTrue(
            err.offending_value is not None,
            "offending_value must be present",
        )

    def test_non_integer_count_raises(self):
        """Sanity — non-integer count column is caught at the API layer too."""
        path = self._csv("good,0,0,0\nhello,ten,0,0\n")
        with self.assertRaises(self.mod.CsvShapeError) as ctx:
            list(self.mod.parse_rows(path))
        self.assertEqual(ctx.exception.row_index, 2)
        self.assertIn("not", ctx.exception.reason.lower())

    def test_empty_prompt_raises(self):
        path = self._csv("good,0,0,0\n   ,0,0,0\n")
        with self.assertRaises(self.mod.CsvShapeError) as ctx:
            list(self.mod.parse_rows(path))
        self.assertEqual(ctx.exception.row_index, 2)
        self.assertIn("prompt", ctx.exception.reason.lower())


class TestCli(unittest.TestCase):
    """2.2 / 2.5 / 2.6 / 2.7 / 2.8 — CLI behavior."""

    def setUp(self):
        self._temp_paths: list[str] = []

    def tearDown(self):
        for path in self._temp_paths:
            try:
                os.remove(path)
            except OSError:
                pass

    def _csv(self, body: str) -> str:
        path = _write_csv(HEADER + body)
        self._temp_paths.append(path)
        return path

    def _run_cli(self, csv_path: str):
        return subprocess.run(
            [sys.executable, PARSER_PATH, csv_path],
            capture_output=True,
        )

    def test_cli_emits_nul_tab_records(self):
        """2.2 — CLI emits NUL/TAB records on stdout."""
        path = self._csv("hello,0,0,0\n")
        result = self._run_cli(path)
        self.assertEqual(
            result.returncode,
            0,
            msg=f"stderr={result.stderr!r}",
        )
        self.assertEqual(result.stdout, b"hello\t0\t0\t0\0")

    def test_cli_catches_trailing_field_shift(self):
        """2.5 — trailing-field shift produces labeled [PARSE-FAIL] and non-zero exit."""
        path = self._csv("good,0,0,0\nhello, how are you doing?,0,0,0\n")
        result = self._run_cli(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        stderr = result.stderr.decode("utf-8", errors="replace")
        self.assertIn("[PARSE-FAIL]", stderr)
        self.assertIn("row 2", stderr)

    def test_cli_catches_non_integer_count(self):
        """2.6 — non-integer count column produces labeled [PARSE-FAIL]."""
        path = self._csv("good,0,0,0\nhello,ten,0,0\n")
        result = self._run_cli(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        stderr = result.stderr.decode("utf-8", errors="replace")
        self.assertIn("[PARSE-FAIL]", stderr)
        self.assertIn("row 2", stderr)
        self.assertIn("ten", stderr)

    def test_cli_catches_empty_prompt(self):
        """2.7 — empty prompt produces labeled [PARSE-FAIL]."""
        path = self._csv("good,0,0,0\n   ,0,0,0\n")
        result = self._run_cli(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        stderr = result.stderr.decode("utf-8", errors="replace")
        self.assertIn("[PARSE-FAIL]", stderr)
        self.assertIn("row 2", stderr)
        self.assertIn("prompt", stderr.lower())

    def test_cli_fail_fast_short_circuits(self):
        """2.8 — fail-fast: first malformed row short-circuits later rows."""
        # Row 2 malformed (trailing-field shift), row 5 malformed (non-integer count).
        body = (
            "good,0,0,0\n"           # row 1 — clean
            "hello, extra,0,0,0\n"   # row 2 — trailing-field shift (5 fields)
            "good,0,0,0\n"           # row 3 — clean
            "good,0,0,0\n"           # row 4 — clean
            "good,ten,0,0\n"         # row 5 — non-integer count
        )
        path = self._csv(body)
        result = self._run_cli(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        stderr = result.stderr.decode("utf-8", errors="replace")
        self.assertIn("row 2", stderr)
        # Row 5 must NOT be mentioned — fail-fast short-circuited at row 2.
        self.assertNotIn("row 5", stderr)


if __name__ == "__main__":
    unittest.main()
