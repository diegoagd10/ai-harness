"""cases_e2e_csv.test.py — structural test for tests-prompts/cases_e2e.csv.

The sibling fixture `tests-prompts/cases_e2e.csv` carries the three RED
regression fixtures (small/concrete, ambiguous/large, complete/large)
that the `change-orchestrator` prompt must route correctly. The
existing `tests-prompts/cases.csv` smoke contract (5 data rows) stays
untouched; the new fixture is a sibling file.

This test:
  1. Verifies the file exists.
  2. Parses it through the project's `parse_csv.py` seam.
  3. Asserts exactly three fixture rows.
  4. Asserts each fixture has the baseline 0,0,0 count triple.
  5. Asserts the three named fixtures anchor the contract:
       - one matches `fibonacci` (small/concrete)
       - one matches `mario kart` / `mario karn` (ambiguous/large)
       - one is the complete Mario Kart brief (complete/large)

Mirrors the structure of `tests-prompts/tests/cases_csv.test.py`.
Runs UNCONDITIONALLY in default CI (no env gate) because it is a
static test against a static file.
"""

from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
import unittest

SCRIPT_DIR = os.path.dirname(__file__)
HELPERS_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
CASES_E2E_CSV = os.path.join(HELPERS_DIR, "cases_e2e.csv")
CASES_CSV = os.path.join(HELPERS_DIR, "cases.csv")
PARSER_PY = os.path.join(HELPERS_DIR, "parse_csv.py")


def _read_csv_lines_skipping_comments(path: str) -> list[str]:
    """Mirror parse_csv.py: lines starting with '#' are skipped."""
    with open(path, encoding="utf-8") as f:
        return [line for line in f if not line.lstrip().startswith("#")]


class TestCasesE2eCsvStructure(unittest.TestCase):
    """cases_e2e.csv shape and contract — three fixtures, baseline counts."""

    def setUp(self):
        if not os.path.isfile(CASES_E2E_CSV):
            self.skipTest(f"cases_e2e.csv not found at {CASES_E2E_CSV}")
        # Mirror parse_csv.py: skip comment lines.
        self.raw_lines = _read_csv_lines_skipping_comments(CASES_E2E_CSV)
        with open(CASES_E2E_CSV, encoding="utf-8", newline="") as f:
            non_comment = (line for line in f if not line.lstrip().startswith("#"))
            in_memory = io.StringIO("".join(non_comment))
            reader = csv.DictReader(in_memory)
            self.rows = list(reader)

    def test_file_has_three_data_rows(self):
        """The new CSV must carry exactly three fixture rows (subtask 3.2)."""
        self.assertEqual(
            len(self.rows),
            3,
            msg=f"expected 3 data rows, got {len(self.rows)}: {self.rows!r}",
        )

    def test_each_row_has_baseline_zero_counts(self):
        """Subtask 3.1 — every row holds the baseline 0,0,0 count triple.

        The routing-shape contract is enforced by `_e2e_assertions`,
        NOT by extra columns. The CSV stays in the existing 4-field wire
        format so every consumer of `parse_csv.py` keeps working.
        """
        for idx, row in enumerate(self.rows):
            with self.subTest(row=idx):
                self.assertEqual(row.get(" tools calls (number)"), "0")
                self.assertEqual(row.get(" skills calls (number)"), "0")
                self.assertEqual(row.get(" sub-agent calls (number)"), "0")

    def test_no_trailing_field_shift(self):
        """parse_csv.py rejects extra columns under row.get(None); same here."""
        for idx, row in enumerate(self.rows):
            with self.subTest(row=idx):
                self.assertIsNone(
                    row.get(None),
                    f"row {idx} has trailing-field shift: {row.get(None)!r}",
                )

    def test_three_named_fixtures_anchor_contract(self):
        """Subtask 3.2 — three named fixtures covering the RED contract.

        At least one matches `fibonacci` (small/concrete).
        At least one matches `mario kart` / `mario karn`
        (ambiguous/large) case-insensitive.
        At least one is the complete Mario Kart brief (3d + concrete
        feature list).
        """
        prompts = [(row.get("prompt") or "").lower() for row in self.rows]

        fib_match = any("fibonacci" in p or "fibonnaci" in p for p in prompts)
        self.assertTrue(fib_match, f"no fibonacci fixture found: {prompts!r}")

        vague_match = any("mario karn" in p or "mario kart" in p for p in prompts)
        self.assertTrue(vague_match, f"no mario kart fixture found: {prompts!r}")

        # Complete brief: at least one fixture mentions 3d AND a concrete
        # feature list (engine + at least one game-feature keyword).
        engine_keywords = ("unity", "unreal", "godot", "engine", "three.js", "webgl")
        feature_keywords = (
            "track",
            "character",
            "physics",
            "multiplayer",
            "ai",
            "karts",
            "race",
            "item",
            "power-up",
            "powerup",
            "controls",
            "menu",
        )
        complete_match = any(
            ("3d" in p) and any(ek in p for ek in engine_keywords) and any(fk in p for fk in feature_keywords)
            for p in prompts
        )
        self.assertTrue(
            complete_match,
            f"no complete Mario Kart fixture (3d + engine + features): {prompts!r}",
        )

    def test_fixtures_are_unique(self):
        """Three rows must be three distinct prompts."""
        prompts = [row.get("prompt") for row in self.rows]
        self.assertEqual(
            len(prompts),
            len(set(prompts)),
            msg=f"duplicate fixture prompts: {prompts!r}",
        )


class TestParserAcceptsCasesE2eCsv(unittest.TestCase):
    """parse_csv.py must accept cases_e2e.csv.

    With the fixture in place:
      - parse_csv exits 0
      - stdout contains 3 NUL-terminated records
      - stderr is empty (no [PARSE-FAIL]).
    """

    def setUp(self):
        if not os.path.isfile(PARSER_PY):
            self.skipTest(f"parse_csv.py not found at {PARSER_PY}")
        if not os.path.isfile(CASES_E2E_CSV):
            self.skipTest(f"cases_e2e.csv not found at {CASES_E2E_CSV}")

    def test_cli_accepts_cases_e2e_csv(self):
        result = subprocess.run(
            [sys.executable, PARSER_PY, CASES_E2E_CSV],
            capture_output=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"parser must accept cases_e2e.csv; stderr={result.stderr!r}",
        )
        # 3 records → 3 NUL bytes in stdout.
        self.assertEqual(
            result.stdout.count(b"\0"),
            3,
            msg=f"expected 3 NUL-terminated records, got stdout={result.stdout!r}",
        )
        # Stderr must NOT contain [PARSE-FAIL] on a well-formed CSV.
        self.assertNotIn(b"[PARSE-FAIL]", result.stderr)

        # Spot-check: at least one record contains fibonacci, at least one
        # contains mario.
        records = result.stdout.split(b"\0")[:-1]
        prompts = [r.split(b"\t")[0].decode("utf-8", errors="replace") for r in records]
        lowered = [p.lower() for p in prompts]
        self.assertTrue(
            any("fibonacci" in p or "fibonnaci" in p for p in lowered),
            f"no fibonacci prompt in records: {prompts!r}",
        )
        self.assertTrue(
            any("mario karn" in p or "mario kart" in p for p in lowered),
            f"no mario kart prompt in records: {prompts!r}",
        )


class TestCasesCsvUntouched(unittest.TestCase):
    """Subtask 3.4 — the existing cases.csv 5-data-rows contract is preserved.

    We assert it via the row count (same assertion
    `tests-prompts/tests/cases_csv.test.py::test_file_has_five_data_rows`
    uses) so a regression on either side trips one of the two tests.
    """

    def setUp(self):
        if not os.path.isfile(CASES_CSV):
            self.skipTest(f"cases.csv not found at {CASES_CSV}")

    def test_cases_csv_still_has_five_data_rows(self):
        with open(CASES_CSV, encoding="utf-8", newline="") as f:
            non_comment = (line for line in f if not line.lstrip().startswith("#"))
            in_memory = io.StringIO("".join(non_comment))
            reader = csv.DictReader(in_memory)
            rows = list(reader)
        self.assertEqual(
            len(rows),
            5,
            msg=f"cases.csv must remain at 5 data rows; got {len(rows)}",
        )


if __name__ == "__main__":
    unittest.main()
