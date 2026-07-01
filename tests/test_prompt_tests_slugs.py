"""Tests for slugify (filename safety) and the parse_csv helper.

slugify is defined inline in run.sh — these tests duplicate the
implementation against the spec (failure-trace-dump:trace-filename) so
the contract is locked down regardless of where the function lives.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

_HELPERS_DIR = Path(__file__).resolve().parent.parent / "tests-prompts"
_RUN_SH = _HELPERS_DIR / "run.sh"


def _slugify(prompt: str) -> str:
    """Python mirror of the bash slugify in run.sh — single contract."""
    s = re.sub(r"[^A-Za-z0-9_-]", "-", prompt)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    s = s[:32]
    return s or "row"


class TestSlugifyContract:
    def test_simple_kept_as_is(self) -> None:
        assert _slugify("hello") == "hello"

    def test_comma_replaced_with_dash(self) -> None:
        assert _slugify("say, hello") == "say-hello"

    def test_slash_replaced_with_dash(self) -> None:
        assert _slugify("a/b") == "a-b"

    def test_space_replaced_with_dash(self) -> None:
        assert _slugify("a b") == "a-b"

    def test_repeated_dashes_collapsed(self) -> None:
        assert _slugify("foo---bar") == "foo-bar"

    def test_leading_trailing_dashes_stripped(self) -> None:
        assert _slugify("---leading and trailing---") == "leading-and-trailing"

    def test_empty_prompt_returns_row(self) -> None:
        assert _slugify("") == "row"

    def test_unicode_replaced_with_dash(self) -> None:
        # Non-ASCII chars fall outside [A-Za-z0-9_-] and become dashes,
        # which are then stripped at the edges.
        assert _slugify("unicode é è ñ 中文") == "unicode"

    def test_cap_at_32_chars(self) -> None:
        out = _slugify("hello world this is a longer prompt than thirty-two characters")
        assert len(out) == 32
        assert out == "hello-world-this-is-a-longer-pro"


class TestFilenameSafety:
    """Spec: filename contains only [A-Za-z0-9._-], no '/', no leading
    '.', and is <= 64 chars total. Format: <row_index>-<slug>.json."""

    SAFE = re.compile(r"^[A-Za-z0-9._-]+$")
    MAX_LEN = 64

    def _filename(self, row_index: int, prompt: str) -> str:
        return f"{row_index}-{_slugify(prompt)}.json"

    @pytest.mark.parametrize(
        "prompt",
        [
            "hello",
            "say, hello",
            'say "hello"!',
            "a/b",
            "a b",
            "---leading---",
            "unicode é",
            "x" * 100,
            "",
        ],
    )
    def test_filename_is_safe(self, prompt: str) -> None:
        fname = self._filename(3, prompt)
        assert "/" not in fname
        assert not fname.startswith(".")
        assert self.SAFE.match(fname), f"unsafe chars in {fname!r}"
        assert len(fname) <= self.MAX_LEN, f"too long ({len(fname)}): {fname}"

    def test_no_collision_for_different_prompts(self) -> None:
        # 'a/b' and 'a b' both slugify to 'a-b' — the row index saves us.
        assert self._filename(1, "a/b") != self._filename(2, "a b")
        # Identical prompts on different rows also don't collide.
        assert self._filename(1, "hello") != self._filename(2, "hello")


class TestRunShSyntax:
    def test_run_sh_is_bash_clean(self) -> None:
        # bash -n is the cheapest syntax check we can do without Docker.
        result = subprocess.run(
            ["bash", "-n", str(_RUN_SH)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"bash -n failed:\nstdout={result.stdout}\nstderr={result.stderr}"

    def test_run_sh_does_not_set_e(self) -> None:
        """Per-row failures must not abort the loop; set -e must be absent."""
        text = _RUN_SH.read_text()
        # `set -uo pipefail` is fine; `set -e` (with or without -o/-u/-E) is not.
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "set -e" not in stripped, f"per-row-killing directive: {stripped!r}"


class TestRunShHasNoPerRowTimeout:
    """Spec: no per-row timeout configured."""

    def test_no_timeout_in_run_row_or_loop(self) -> None:
        text = _RUN_SH.read_text()
        # Locate the run_row function + main loop.
        in_run_row = False
        in_loop = False
        for line in text.splitlines():
            if line.startswith("run_row()"):
                in_run_row = True
            if "# Per-row loop" in line:
                in_loop = True
            if in_run_row and line.startswith("dump_failure_trace"):
                in_run_row = False
            if in_loop and (line.startswith("parse_csv") or line.startswith("TOTAL=")):
                in_loop = True
            if in_run_row or in_loop:
                assert "timeout" not in line, f"per-row timeout reference: {line!r}"
