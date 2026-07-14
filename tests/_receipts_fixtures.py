"""Shared pytest fixtures for receipt tests."""

from __future__ import annotations

import os
import sys

import pytest


@pytest.fixture
def subprocess_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Strip subprocess-inherited env noise so tests stay deterministic.

    Removes the test-process secret variables the executor would
    otherwise treat as policy secrets while running real subprocesses.
    """

    for key in list(os.environ.keys()):
        if key.startswith(("MY_TEST_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY")):
            monkeypatch.delenv(key, raising=False)
    # Ensure Python interpreters share a deterministic baseline.
    monkeypatch.setenv("PYTHONUNBUFFERED", "1")
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    return dict(os.environ)
