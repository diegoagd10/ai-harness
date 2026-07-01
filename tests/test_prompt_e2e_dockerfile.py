"""Static tests for tests-prompts/Dockerfile COPY list after the
prompt-e2e-red-tests change.

The Dockerfile carries only the helpers + CSV that run.sh invokes at
container runtime. Any helper or fixture added to the prompt-E2E
suite must be COPYed here too — the comment at tests-prompts/Dockerfile:43
warns that `parse_csv: command not found` (or equivalent) is the
container-side symptom when a COPY is forgotten.

This test asserts the COPY lines for the new files exist. It does
NOT build the image (that's the responsibility of docker-test.sh);
it guards the source so a regression on either COPY is caught
before the container build.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_DOCKERFILE = Path(__file__).resolve().parent.parent / "tests-prompts" / "Dockerfile"


@pytest.fixture(scope="module")
def dockerfile_text() -> str:
    if not _DOCKERFILE.is_file():
        pytest.skip(f"Dockerfile not found at {_DOCKERFILE}")
    return _DOCKERFILE.read_text()


class TestDockerfileCopiesNewFiles:
    """Subtasks 5.1 + 5.2 — the new helpers and CSV land in the image."""

    def test_copy_cases_e2e_csv_present(self, dockerfile_text: str) -> None:
        # Subtask 5.1 — cases_e2e.csv must be COPYed next to cases.csv
        # so the in-container run.sh (CASES_CSV_E2E second loop, task 6)
        # can read it.
        pattern = r"^\s*COPY\s+tests-prompts/cases_e2e\.csv\s+/tests-prompts/cases_e2e\.csv\s*$"
        assert re.search(pattern, dockerfile_text, re.MULTILINE), (
            "Dockerfile must COPY tests-prompts/cases_e2e.csv to "
            "/tests-prompts/cases_e2e.csv next to the existing cases.csv COPY"
        )

    def test_copy_e2e_assertions_present(self, dockerfile_text: str) -> None:
        # Subtask 5.2 — _e2e_assertions.py must be COPYed next to
        # _extractor.py because run.sh's E2E second loop pipes traces
        # through this helper.
        pattern = (
            r"^\s*COPY\s+tests-prompts/_e2e_assertions\.py"
            r"\s+/tests-prompts/_e2e_assertions\.py\s*$"
        )
        assert re.search(pattern, dockerfile_text, re.MULTILINE), (
            "Dockerfile must COPY tests-prompts/_e2e_assertions.py to "
            "/tests-prompts/_e2e_assertions.py next to the existing "
            "_extractor.py COPY"
        )

    def test_copy_e2e_runner_present(self, dockerfile_text: str) -> None:
        # _e2e_runner.py is the per-fixture orchestrator routing decision
        # helper used by the CASES_CSV_E2E second loop (task 6).
        pattern = (
            r"^\s*COPY\s+tests-prompts/_e2e_runner\.py"
            r"\s+/tests-prompts/_e2e_runner\.py\s*$"
        )
        assert re.search(pattern, dockerfile_text, re.MULTILINE), (
            "Dockerfile must COPY tests-prompts/_e2e_runner.py to "
            "/tests-prompts/_e2e_runner.py so run.sh's CASES_CSV_E2E "
            "second loop can call it"
        )

    def test_source_files_referenced_by_copy_exist(self) -> None:
        # The COPY paths reference real files on disk — a typo here would
        # surface as "file not found" at docker build time, but checking
        # locally shortens the feedback loop.
        repo = Path(__file__).resolve().parent.parent
        for rel in (
            "tests-prompts/cases_e2e.csv",
            "tests-prompts/_e2e_assertions.py",
            "tests-prompts/_e2e_runner.py",
        ):
            assert (repo / rel).is_file(), f"{rel} missing on host"

    def test_chmod_includes_new_files(self, dockerfile_text: str) -> None:
        # The Dockerfile's chmod block lists the helper files. New helpers
        # must be added so they are executable in the container. CSV is
        # data, not executable, so it is intentionally NOT chmoded.
        chmod_match = re.search(
            r"RUN\s+chmod\s+\+x(.+?)(?=\n\s*\n|\Z)",
            dockerfile_text,
            re.DOTALL,
        )
        assert chmod_match, "Dockerfile must have a RUN chmod +x block"
        chmod_body = chmod_match.group(1)
        assert "_e2e_assertions.py" in chmod_body, (
            "_e2e_assertions.py must be added to the RUN chmod +x block so it is executable in the container"
        )
        assert "_e2e_runner.py" in chmod_body, (
            "_e2e_runner.py must be added to the RUN chmod +x block so it is executable in the container"
        )


class TestDockerfileUntouchedExistingCopies:
    """Existing COPY lines and chmod entries must remain intact."""

    def test_existing_copy_lines_intact(self, dockerfile_text: str) -> None:
        # The original COPY block (run.sh, cases.csv, _extractor.py,
        # parse_csv.py, _dump_parse_trace.py) must NOT have been
        # removed when the new COPYs were added.
        for rel in (
            "tests-prompts/run.sh",
            "tests-prompts/cases.csv",
            "tests-prompts/_extractor.py",
            "tests-prompts/parse_csv.py",
            "tests-prompts/_dump_parse_trace.py",
        ):
            assert f"COPY {rel}" in dockerfile_text, f"existing COPY line for {rel} was removed — restore it"

    def test_existing_chmod_lines_intact(self, dockerfile_text: str) -> None:
        # The chmod block must still cover all original helper files.
        chmod_match = re.search(
            r"RUN\s+chmod\s+\+x(.+?)(?=\n\s*\n|\Z)",
            dockerfile_text,
            re.DOTALL,
        )
        assert chmod_match
        chmod_body = chmod_match.group(1)
        for helper in (
            "/tests-prompts/run.sh",
            "/tests-prompts/_extractor.py",
            "/tests-prompts/parse_csv.py",
            "/tests-prompts/_dump_parse_trace.py",
        ):
            assert helper in chmod_body, f"{helper} missing from chmod block — restore it"
