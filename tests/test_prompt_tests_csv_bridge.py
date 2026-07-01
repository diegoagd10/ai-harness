"""Tests for the parse_csv bridge and the bash loop that consumes it.

These tests lock down multiline-CSV support: a prompt that contains a
newline must survive parse_csv and the bash `while read` loop as ONE
record, not as two split records.

The bridge in `tests-prompts/run.sh` is a Python helper that streams
parsed CSV rows on stdout, then a bash `while read -d ''` loop consumes
those records. The old bridge used tab/newline separation which split a
multiline prompt across two loop iterations; the contract now requires
NUL-delimited records so any byte sequence (including newlines) is safe.
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

_HEADER = "prompt, tools calls (number), skills calls (number), sub-agent calls (number)"


def _rows_to_csv(rows: list[tuple[str, str, str, str]]) -> str:
    """Build a CSV body with the v1 header + given data rows.

    Uses Python's csv module so RFC 4180 escaping (doubled quotes,
    quoted fields with commas or newlines) is generated correctly.
    Avoids embedding literal CSV text in Python source so we never have
    to worry about quote collisions with f-string delimiters.
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "prompt",
            " tools calls (number)",
            " skills calls (number)",
            " sub-agent calls (number)",
        ]
    )
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _write_csv(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "cases.csv"
    p.write_text(body)
    return p


def _python_parse(path: Path) -> list[tuple[str, str, str, str]]:
    """Python mirror of the run.sh parse_csv bridge.

    Emits one (prompt, tools, skills, subs) tuple per non-blank data row.
    Multiline prompts are preserved as a single field (no embedded
    newlines are used as record separators).
    """
    rows: list[tuple[str, str, str, str]] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            prompt = (row.get("prompt") or "").strip()
            if not prompt:
                continue
            tools = (row.get(" tools calls (number)") or "0").strip() or "0"
            skills = (row.get(" skills calls (number)") or "0").strip() or "0"
            subs = (row.get(" sub-agent calls (number)") or "0").strip() or "0"
            rows.append((prompt, tools, skills, subs))
    return rows


# ---------------------------------------------------------------------------
# Tests for parse_csv's logical behavior
# ---------------------------------------------------------------------------


class TestParseCsvMultilineContract:
    """parse_csv must yield ONE record per data row, even when a prompt
    contains newlines, commas, or quotes.
    """

    def test_multiline_prompt_is_one_record(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv(
                [
                    ("line one\nline two", "1", "0", "0"),
                    ("hello", "0", "0", "0"),
                ]
            ),
        )
        rows = _python_parse(csv_path)
        assert len(rows) == 2, f"expected 2 rows, got {len(rows)}: {rows!r}"
        # First row preserves the multiline prompt as a single field.
        assert rows[0][0] == "line one\nline two"
        assert rows[0][1:] == ("1", "0", "0")
        # Second row is the simple hello row.
        assert rows[1] == ("hello", "0", "0", "0")

    def test_three_multiline_prompts_preserve_newlines(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv(
                [
                    ("alpha\nbeta", "1", "2", "3"),
                    ("gamma\ndelta\nepsilon", "4", "5", "6"),
                    ("zeta\neta", "7", "8", "9"),
                ]
            ),
        )
        rows = _python_parse(csv_path)
        assert len(rows) == 3, f"expected 3 rows, got {len(rows)}: {rows!r}"
        assert rows[0][0] == "alpha\nbeta"
        assert rows[1][0] == "gamma\ndelta\nepsilon"
        assert rows[2][0] == "zeta\neta"
        assert [r[1:] for r in rows] == [
            ("1", "2", "3"),
            ("4", "5", "6"),
            ("7", "8", "9"),
        ]

    def test_comma_in_prompt_preserved(self, tmp_path: Path) -> None:
        # csv.writer will quote this field because it contains a comma.
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv([("say, hello", "1", "0", "0")]),
        )
        rows = _python_parse(csv_path)
        assert rows == [("say, hello", "1", "0", "0")]

    def test_quote_in_prompt_preserved(self, tmp_path: Path) -> None:
        # csv.writer doubles the inner quotes per RFC 4180.
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv([('say "hello"', "1", "0", "0")]),
        )
        rows = _python_parse(csv_path)
        assert len(rows) == 1
        assert rows[0][0] == 'say "hello"'
        assert rows[0][1:] == ("1", "0", "0")

    def test_blank_line_skipped(self, tmp_path: Path) -> None:
        # One header + a blank line + two data rows.
        body = _HEADER + "\n" + "hello,0,0,0" + "\n\n" + "world,0,0,0" + "\n"
        csv_path = _write_csv(tmp_path, body)
        rows = _python_parse(csv_path)
        assert len(rows) == 2
        assert rows[0][0] == "hello"
        assert rows[1][0] == "world"

    def test_existing_cases_csv_still_parses_to_one_row(self) -> None:
        # The committed cases.csv must continue to produce exactly one row.
        repo_csv = Path(__file__).resolve().parent.parent / "tests-prompts" / "cases.csv"
        rows = _python_parse(repo_csv)
        assert rows == [("hello", "0", "0", "0")]


# ---------------------------------------------------------------------------
# Tests for the bash loop reading NUL-delimited records
# ---------------------------------------------------------------------------


class TestBashNulDelimitedLoop:
    """The bash `while IFS=$'\\t' read -r -d ''` loop must consume one
    CSV record per iteration, preserving embedded newlines in prompts.

    Wire format: TAB between fields, NUL between records. So each record
    is `<prompt>\\t<tools>\\t<skills>\\t<subs>\\0` and the bash loop
    reads up to NUL then splits by TAB.
    """

    # The bridge output uses TAB between fields and NUL between records.
    # The loop uses `read -d ''` (read until NUL) with IFS=tab. We feed
    # the payload via stdin (not via $1) so NUL bytes survive the
    # command-line untouched.
    BASH_SNIPPET = r"""
        set -uo pipefail
        ROW_INDEX=0
        while IFS=$'\t' read -r -d '' PROMPT EXP_TOOLS EXP_SKILLS EXP_SUBAGENTS; do
            ROW_INDEX=$((ROW_INDEX + 1))
            printf 'ROW %d prompt=<%s> t=%s s=%s u=%s\n' \
                "$ROW_INDEX" "$PROMPT" "$EXP_TOOLS" "$EXP_SKILLS" "$EXP_SUBAGENTS"
        done
    """

    def _run_bash(self, payload: bytes) -> str:
        result = subprocess.run(
            ["bash", "-c", self.BASH_SNIPPET],
            input=payload,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, f"bash failed:\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        # Decode bytes -> str (errors='replace' to be safe with any NUL that
        # might leak into printf output; in practice ROW lines are ASCII).
        return result.stdout.decode("utf-8", errors="replace")

    @staticmethod
    def _data_rows(out: str) -> list[str]:
        """Extract ROW n lines from bash output.

        ROW lines start with 'ROW N prompt=<' and end at the FIRST newline
        (the printf %s converts each field but the prompt field may itself
        contain newlines). We use a regex that captures one ROW line up
        to its terminating 'u=<digits>\n'.
        """
        # Each ROW line ends with 'u=<digit(s)>\n' (or u= followed by whatever).
        return re.findall(r"ROW \d+ prompt=<.*?> t=\S* s=\S* u=\S*", out, re.DOTALL)

    def test_simple_records_no_newlines(self) -> None:
        # Wire format: TAB between fields, NUL between records.
        #   <hello>\t<0>\t<0>\t<0>\0<world>\t<1>\t<2>\t<3>\0
        payload = b"hello\t0\t0\t0\x00world\t1\t2\t3\x00"
        out = self._run_bash(payload)
        assert self._data_rows(out) == [
            "ROW 1 prompt=<hello> t=0 s=0 u=0",
            "ROW 2 prompt=<world> t=1 s=2 u=3",
        ]

    def test_multiline_prompt_is_one_record(self) -> None:
        # Multiline prompt is one field; NUL is the record separator.
        # <line one\nline two>\t<1>\t<0>\t<0>\0<hello>\t<0>\t<0>\t<0>\0
        payload = b"line one\nline two\t1\t0\t0\x00hello\t0\t0\t0\x00"
        out = self._run_bash(payload)
        rows = self._data_rows(out)
        assert len(rows) == 2, f"expected 2 records, got {len(rows)}: {rows!r}"
        assert rows[0] == "ROW 1 prompt=<line one\nline two> t=1 s=0 u=0"
        assert rows[1] == "ROW 2 prompt=<hello> t=0 s=0 u=0"

    def test_three_multiline_records(self) -> None:
        # Three records, each with a multiline prompt.
        payload = b"alpha\nbeta\t1\t2\t3\x00gamma\ndelta\nepsilon\t4\t5\t6\x00zeta\neta\t7\t8\t9\x00"
        out = self._run_bash(payload)
        rows = self._data_rows(out)
        assert len(rows) == 3, f"expected 3 records, got {len(rows)}: {rows!r}"
        assert rows[0] == "ROW 1 prompt=<alpha\nbeta> t=1 s=2 u=3"
        assert rows[1] == "ROW 2 prompt=<gamma\ndelta\nepsilon> t=4 s=5 u=6"
        assert rows[2] == "ROW 3 prompt=<zeta\neta> t=7 s=8 u=9"

    def test_total_count_via_nul_count(self) -> None:
        # The runner derives TOTAL by counting NULs. One NUL per record.
        # We feed 3 records (3 NULs) and confirm `tr -cd '\0' | wc -c`
        # returns 3.
        payload = b"a\t0\t0\t0\x00b\t0\t0\t0\x00c\t0\t0\t0\x00"
        result = subprocess.run(
            ["bash", "-c", "tr -cd '\\0' | wc -c"],
            input=payload,
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
        out = result.stdout.decode("utf-8", "replace").strip()
        assert out == "3", f"expected 3 NULs (3 records), got {out!r}"


# ---------------------------------------------------------------------------
# Tests for parse_csv's wire format (NUL-delimited records)
# ---------------------------------------------------------------------------


class TestParseCsvWireFormat:
    """parse_csv must emit TAB-fielded, NUL-terminated 4-field records
    on stdout.

    Wire format: <prompt>\\t<tools>\\t<skills>\\t<subs>\\0
    The bridge is invoked from run.sh; its wire format is the contract
    between Python and the bash `read -d ''` loop.
    """

    # Inline the fixed parse_csv body so the test stays in sync with the
    # contract we want to enforce. The actual implementation lives in
    # run.sh; this body MUST match what the runner ships.
    _BRIDGE_BODY = (
        "import csv, sys\n"
        "path = sys.argv[1]\n"
        "with open(path, newline='') as f:\n"
        "    reader = csv.DictReader(f)\n"
        "    field_tools = ' tools calls (number)'\n"
        "    field_skills = ' skills calls (number)'\n"
        "    field_subs = ' sub-agent calls (number)'\n"
        "    for row in reader:\n"
        "        prompt = (row.get('prompt') or '').strip()\n"
        "        if not prompt: continue\n"
        "        tools = (row.get(field_tools) or '0').strip() or '0'\n"
        "        skills = (row.get(field_skills) or '0').strip() or '0'\n"
        "        subs = (row.get(field_subs) or '0').strip() or '0'\n"
        "        sys.stdout.buffer.write("
        "f'{prompt}\\t{tools}\\t{skills}\\t{subs}\\x00'.encode('utf-8'))\n"
    )

    def _invoke_bridge(self, csv_path: Path) -> bytes:
        result = subprocess.run(
            ["python3", "-", str(csv_path)],
            input=self._BRIDGE_BODY.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, f"bridge invocation failed:\nstderr={result.stderr.decode(errors='replace')}"
        return result.stdout

    def test_bridge_emits_nul_as_record_separator(self, tmp_path: Path) -> None:
        # The bug the validator caught: a prompt with a newline caused
        # the bridge to emit a literal \\n inside the record, which the
        # bash read loop treated as a record boundary. The bridge must
        # use NUL as the record separator.
        #
        # A prompt with an embedded newline legitimately contains a
        # newline byte — what must NOT happen is for that newline to be
        # a record boundary. We split the output by NUL and confirm each
        # record has exactly 4 tab-separated fields.
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv(
                [
                    ("line one\nline two", "1", "0", "0"),
                    ("hello", "0", "0", "0"),
                ]
            ),
        )
        out = self._invoke_bridge(csv_path)
        records = [r for r in out.split(b"\x00") if r]
        assert len(records) == 2, f"expected 2 NUL-delimited records, got {len(records)}: {out!r}"
        for i, record in enumerate(records, start=1):
            fields = record.split(b"\t")
            assert len(fields) == 4, (
                f"record {i} should have 4 tab-separated fields, got {len(fields)}: {record!r} (raw: {out!r})"
            )
        # The first record's prompt field is the multiline prompt.
        assert records[0].split(b"\t")[0] == b"line one\nline two"
        # The second record is the simple hello row.
        assert records[1] == b"hello\t0\t0\t0"

    def test_bridge_emits_one_nul_per_record(self, tmp_path: Path) -> None:
        # Each record contributes exactly one NUL terminator (after subs).
        # So total NUL count = row count.
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv(
                [
                    ("line one\nline two", "1", "0", "0"),
                    ("hello", "0", "0", "0"),
                    ("another\nmulti\nline", "2", "3", "4"),
                ]
            ),
        )
        out = self._invoke_bridge(csv_path)
        nul_count = out.count(b"\x00")
        assert nul_count == 3, f"expected 3 NULs (3 records), got {nul_count}: {out!r}"

    def test_bridge_preserves_prompt_bytes_verbatim(self, tmp_path: Path) -> None:
        # A prompt with newlines, commas, and quotes must appear verbatim
        # in the bridge output (no escaping, no truncation).
        prompt = 'multi\nline, with "quotes" and more'
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv([(prompt, "1", "2", "3")]),
        )
        out = self._invoke_bridge(csv_path)
        # The prompt bytes should appear intact in the output.
        assert prompt.encode("utf-8") in out, f"prompt not preserved verbatim in bridge output: {out!r}"


# ---------------------------------------------------------------------------
# Regression: the LIVE parse_csv function shipped in run.sh must satisfy
# the NUL record-separator contract. This is the test the validator was
# effectively running — it must FAIL on the buggy bridge and PASS once
# run.sh is fixed.
# ---------------------------------------------------------------------------


_RUN_SH_PATH = Path(__file__).resolve().parent.parent / "tests-prompts" / "run.sh"


def _extract_parse_csv_body(run_sh_text: str) -> str:
    """Pull the Python body of parse_csv() out of run.sh source.

    The function is defined as a here-doc between the lines
    'python3 - "$path" <<'PYEOF'' and the line 'PYEOF'.
    """
    start = run_sh_text.find("python3 - \"$path\" <<'PYEOF'")
    assert start != -1, "could not find parse_csv's python3 heredoc in run.sh"
    start = run_sh_text.find("\n", start) + 1
    end = run_sh_text.find("PYEOF", start)
    assert end != -1, "could not find PYEOF terminator in run.sh"
    return run_sh_text[start:end]


class TestLiveRunShBridge:
    """End-to-end check that the parse_csv actually shipped in run.sh
    emits NUL-delimited records (the bug the validator caught).
    """

    def test_run_sh_uses_nul_record_separator(self, tmp_path: Path) -> None:
        run_sh_text = _RUN_SH_PATH.read_text()
        body = _extract_parse_csv_body(run_sh_text)
        # Sanity: the body should reference the field names we expect.
        assert "tools calls (number)" in body, "parse_csv body is missing the expected header; run.sh changed?"
        # Invoke the live parse_csv body and confirm NUL-delimited output.
        csv_path = _write_csv(
            tmp_path,
            _rows_to_csv(
                [
                    ("line one\nline two", "1", "0", "0"),
                    ("hello", "0", "0", "0"),
                ]
            ),
        )
        result = subprocess.run(
            ["python3", "-", str(csv_path)],
            input=body.encode("utf-8"),
            capture_output=True,
            timeout=10,
        )
        assert result.returncode == 0, f"parse_csv failed:\nstderr={result.stderr.decode(errors='replace')}"
        out = result.stdout
        records = [r for r in out.split(b"\x00") if r]
        assert len(records) == 2, (
            "run.sh parse_csv is not NUL-delimited: a prompt containing a "
            "newline is split across records. Validator finding reproduced.\n"
            f"raw output: {out!r}"
        )
        # Each record has exactly 4 tab-separated fields.
        for i, record in enumerate(records, start=1):
            fields = record.split(b"\t")
            assert len(fields) == 4, f"record {i} has {len(fields)} tab-separated fields (expected 4): {record!r}"
        # The first record's prompt field preserves the embedded newline.
        assert records[0].split(b"\t")[0] == b"line one\nline two"

    def test_run_sh_uses_read_d_null_in_loop(self) -> None:
        # The bash loop MUST use `read -d ''` so the NUL-delimited bridge
        # output is consumed record-by-record. Without -d '', the read
        # would split on \n and reproduce the bug.
        text = _RUN_SH_PATH.read_text()
        assert re.search(r"read\s+-r\s+-d\s+''", text), (
            "run.sh's per-row loop does not use `read -r -d ''`; the "
            "NUL-delimited bridge output would be split on newlines, "
            "reproducing the multiline-CSV bug."
        )
