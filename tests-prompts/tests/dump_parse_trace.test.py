#!/usr/bin/env python3
"""Unit tests for tests-prompts/_dump_parse_trace.py.

The validator finding that drove this slice:
  parse-time CSV failures do not write the required structured artifact
  into $LOGS_DIR / dump_failure_trace-equivalent output.

The PRD contract (prd.md "Surface the fix in the row's failure trace"):
  When a row is rejected by parse_csv, write a structured entry to
  $LOGS_DIR (same shape as dump_failure_trace) so CI scrapers and
  humans see the same artifact regardless of where the failure
  originates.

This test verifies the helper seam that produces that artifact. It
exercises the helper directly (no Docker, no model, no shell
container-required guard) and asserts:

  DPT.1 — calls the helper CLI on a synthesized parse-fail stderr
          file; the helper exits 0
  DPT.2 — exactly one *.json file appears in the supplied LOGS_DIR
  DPT.3 — the file's basename encodes the parsed row_index
          (e.g. parse-fail-2.json)
  DPT.4 — the JSON document is valid and contains the keys
          source/row_index/stderr with the expected types
  DPT.5 — when the helper is invoked on a parse_csv.py real-run stderr
          (subprocess end-to-end), it produces the same artifact
          (run.sh integration: parse_csv fails, helper writes
          LOGS_DIR/parse-fail-<N>.json)

Run on the host, no Docker, no model — same seams as the rest of
tests-prompts/tests/*.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# tests-prompts/tests/dump_parse_trace.test.py -> tests-prompts/_dump_parse_trace.py
HELPER_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "_dump_parse_trace.py")
)
# For the integration check we also reach into parse_csv.py.
PARSER_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "parse_csv.py")
)


def _write_stderr(text: str) -> str:
    """Write `text` to a temp file and return its path."""
    fd, path = tempfile.mkstemp(prefix="dump_parse_trace_stderr_", suffix=".txt")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _write_csv_unfixed() -> str:
    """Write a CSV that parse_csv.py rejects: row 2 has an unquoted
    comma inside the prompt → trailing-field shift.

    IMPORTANT: write the file as a raw string. Using csv.writer would
    silently add the RFC-4180 quoting parse_csv.py needs to accept the
    row, defeating the test's purpose. The contract here is
    deliberately unfixed-shaped so parse_csv.py must reject it.
    """
    fd, path = tempfile.mkstemp(prefix="dump_parse_trace_csv_", suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write(
            "prompt, tools calls (number), skills calls (number), "
            "sub-agent calls (number)\n"
            "hello,0,0,0\n"
            "hello, how are you doing?,0,0,0\n"
        )
    return path


class TestHelperExists(unittest.TestCase):
    """DPT.0 — the helper seam exists on disk."""

    def test_helper_file_exists(self):
        self.assertTrue(
            os.path.isfile(HELPER_PATH),
            f"_dump_parse_trace.py must exist at {HELPER_PATH}",
        )


class TestHelperInvariants(unittest.TestCase):
    """DPT.1 / DPT.2 / DPT.3 / DPT.4 — helper is invokable and writes the expected artifact."""

    def setUp(self):
        if not os.path.isfile(HELPER_PATH):
            self.skipTest(f"helper not found at {HELPER_PATH}")
        self.logs_dir = tempfile.mkdtemp(prefix="dump_parse_trace_logs_")
        self._stderr_paths: list[str] = []

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.logs_dir, ignore_errors=True)
        except Exception:
            pass
        for p in self._stderr_paths:
            try:
                os.remove(p)
            except OSError:
                pass

    def _run_helper(self, stderr_text: str) -> subprocess.CompletedProcess:
        stderr_path = _write_stderr(stderr_text)
        self._stderr_paths.append(stderr_path)
        return subprocess.run(
            [sys.executable, HELPER_PATH, self.logs_dir, stderr_path],
            capture_output=True,
        )

    def test_helper_exits_zero_on_synthesized_parse_fail_stderr(self):
        """DPT.1 — synthesized parse-fail stderr → exit 0, one artifact."""
        stderr_text = (
            "[PARSE-FAIL] row 2 (hello): trailing-field shift "
            "(extra columns beyond header) — got '0'\n"
        )
        result = self._run_helper(stderr_text)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"helper must exit 0 on synthesized parse-fail stderr; "
                f"stderr={result.stderr.decode('utf-8', errors='replace')!r}"
            ),
        )
        artifacts = sorted(Path(self.logs_dir).glob("*.json"))
        self.assertEqual(
            len(artifacts),
            1,
            msg=f"expected exactly 1 artifact, got {artifacts!r}",
        )

    def test_helper_writes_artifact_with_row_index_in_basename(self):
        """DPT.3 — basename encodes the parsed row_index (parse-fail-<N>.json)."""
        stderr_text = "[PARSE-FAIL] row 7 (prompt-prefix): empty prompt — got ''\n"
        self._run_helper(stderr_text)
        artifacts = sorted(Path(self.logs_dir).glob("parse-fail-*.json"))
        self.assertEqual(
            len(artifacts),
            1,
            msg=f"expected exactly one parse-fail-*.json artifact, got {artifacts!r}",
        )
        self.assertEqual(
            artifacts[0].name,
            "parse-fail-7.json",
            msg=f"basename must encode row index 7; got {artifacts[0].name!r}",
        )

    def test_helper_json_document_has_required_keys(self):
        """DPT.4 — JSON document has source/row_index/stderr with expected types."""
        stderr_text = (
            "[PARSE-FAIL] row 2 (hello): trailing-field shift "
            "(extra columns beyond header) — got '0'\n"
        )
        self._run_helper(stderr_text)
        artifact = next(Path(self.logs_dir).glob("parse-fail-*.json"))
        with open(artifact, "r", encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc.get("source"), "parse_csv")
        self.assertEqual(doc.get("row_index"), 2)
        self.assertIsInstance(doc.get("stderr"), str)
        self.assertIn("[PARSE-FAIL] row 2", doc["stderr"])
        # The full stderr text must be present so a CI scraper can read
        # the reason without re-running parse_csv.
        self.assertIn("trailing-field shift", doc["stderr"])

    def test_helper_handles_multi_line_stderr_with_only_first_line_mattering(self):
        """DPT.4-extra — only the row index matters for the filename;
        the full stderr is preserved verbatim."""
        stderr_text = (
            "[PARSE-FAIL] row 4 (Hola!!): prompt is empty — got ''\n"
            "[hint] consider quoting fields per RFC-4180\n"
        )
        self._run_helper(stderr_text)
        artifacts = sorted(Path(self.logs_dir).glob("parse-fail-*.json"))
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].name, "parse-fail-4.json")
        with open(artifacts[0], "r", encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc["row_index"], 4)
        self.assertIn("consider quoting fields", doc["stderr"])


class TestHelperEndToEnd(unittest.TestCase):
    """DPT.5 — integration: a real parse_csv.py failure produces an
    artifact when the helper sees its captured stderr.

    This is the run.sh-shape integration without invoking run.sh (the
    container-guard would block a host invocation). It exercises:
       1. parse_csv.py on a deliberately malformed CSV → exit 1, stderr
       2. helper on that stderr file → 1 artifact in logs dir
    """

    def setUp(self):
        if not os.path.isfile(HELPER_PATH):
            self.skipTest(f"helper not found at {HELPER_PATH}")
        if not os.path.isfile(PARSER_PATH):
            self.skipTest(f"parse_csv.py not found at {PARSER_PATH}")
        self.logs_dir = tempfile.mkdtemp(prefix="dump_parse_trace_logs_e2e_")
        self._tmp_paths: list[str] = []
        self._tmp_dirs: list[str] = []

    def tearDown(self):
        import shutil
        for d in [self.logs_dir] + self._tmp_dirs:
            try:
                shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        for p in self._tmp_paths:
            try:
                os.remove(p)
            except OSError:
                pass

    def test_real_parse_csv_failure_produces_logs_artifact(self):
        """DPT.5 — parse_csv.py on a malformed CSV → helper writes a trace."""
        bad_csv = _write_csv_unfixed()
        self._tmp_paths.append(bad_csv)
        # 1) parse_csv.py fails with stderr.
        parse_proc = subprocess.run(
            [sys.executable, PARSER_PATH, bad_csv],
            capture_output=True,
        )
        self.assertNotEqual(
            parse_proc.returncode,
            0,
            msg=(
                "parse_csv.py must reject the unfixed CSV; "
                f"stderr={parse_proc.stderr.decode('utf-8', errors='replace')!r}"
            ),
        )
        # Persist stderr so the helper can read it.
        stderr_fd, stderr_path = tempfile.mkstemp(
            prefix="dump_parse_trace_real_stderr_", suffix=".txt"
        )
        self._tmp_paths.append(stderr_path)
        with os.fdopen(stderr_fd, "wb") as f:
            f.write(parse_proc.stderr)
        # 2) Run the helper.
        helper_proc = subprocess.run(
            [sys.executable, HELPER_PATH, self.logs_dir, stderr_path],
            capture_output=True,
        )
        self.assertEqual(
            helper_proc.returncode,
            0,
            msg=(
                f"helper must exit 0 on a real parse_csv stderr; "
                f"helper_stderr={helper_proc.stderr.decode('utf-8', errors='replace')!r}"
            ),
        )
        # 3) Artifact is present, encodes row 2, documents the failure.
        artifacts = sorted(Path(self.logs_dir).glob("parse-fail-*.json"))
        self.assertEqual(
            len(artifacts),
            1,
            msg=f"expected exactly one artifact; got {artifacts!r}",
        )
        with open(artifacts[0], "r", encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(doc.get("source"), "parse_csv")
        self.assertEqual(doc.get("row_index"), 2)
        self.assertIsInstance(doc.get("stderr"), str)
        self.assertIn("[PARSE-FAIL]", doc["stderr"])


class TestHelperRobustness(unittest.TestCase):
    """The helper MUST degrade safely on bad input so run.sh never gets
    blocked by an artifact-writing failure."""

    def setUp(self):
        if not os.path.isfile(HELPER_PATH):
            self.skipTest(f"helper not found at {HELPER_PATH}")
        self.logs_dir = tempfile.mkdtemp(prefix="dump_parse_trace_logs_robust_")
        self._stderr_paths: list[str] = []

    def tearDown(self):
        import shutil
        try:
            shutil.rmtree(self.logs_dir, ignore_errors=True)
        except Exception:
            pass
        for p in self._stderr_paths:
            try:
                os.remove(p)
            except OSError:
                pass

    def test_empty_stderr_does_not_crash(self):
        """Helper tolerates empty / unreadable stderr: writes nothing,
        exits non-zero so the caller can decide. run.sh will treat it
        as 'no artifact' and continue exit-1'ing with the existing
        [PARSE-FAIL] propagation. We tolerate any non-stdout error
        gracefully — we do NOT want run.sh stuck on a helper crash."""
        stderr_path = _write_stderr("")
        self._stderr_paths.append(stderr_path)
        result = subprocess.run(
            [sys.executable, HELPER_PATH, self.logs_dir, stderr_path],
            capture_output=True,
        )
        # Either nothing written (artifact absent), or a 'no [PARSE-FAIL]'
        # warning on stderr — both are acceptable degradation modes for
        # the helper seam. The MUST is "no traceback on stdout".
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(
            len(list(Path(self.logs_dir).glob("*.json"))),
            0,
            msg=(
                "with no parse-fail signal in stderr, the helper must NOT "
                "fabricate an artifact — run.sh will rely on this to "
                "distinguish 'real parse failure' from 'helper noise'."
            ),
        )


if __name__ == "__main__":
    unittest.main()
