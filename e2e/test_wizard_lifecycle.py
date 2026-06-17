"""Wizard bypass lifecycle: ai-harness install --all / uninstall --all.

Covers state-file assertions after non-interactive install and uninstall —
verifying that the ``--all`` bypass correctly writes and clears
``~/.ai-harness/state.json``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import harness

REPO_ROOT = Path(__file__).resolve().parent.parent

STATE_DIR = ".ai-harness"
STATE_FILE = ".ai-harness/state.json"


def _bin_path(bin_dir: str) -> str:
    """Prepend *bin_dir* to PATH."""
    return f"{bin_dir}:{os.environ.get('PATH', '')}"


def _assert_state_file(home: str, expected: set[str], label: str) -> None:
    """Assert ``~/.ai-harness/state.json`` exists with the expected installed set.

    The order of entries in the JSON array is not significant.
    """
    state_path = Path(home) / STATE_FILE
    if not state_path.is_file():
        raise AssertionError(f"{label}: state file missing — {state_path}")
    try:
        doc = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AssertionError(f"{label}: state file is not valid JSON") from exc
    installed = set(doc.get("installed", []))
    if installed != expected:
        raise AssertionError(
            f"{label}: unexpected installed set\n  expected: {sorted(expected)}\n  got:      {sorted(installed)}"
        )


def _assert_state_file_missing(home: str, label: str) -> None:
    """Assert ``~/.ai-harness/state.json`` does not exist."""
    state_path = Path(home) / STATE_FILE
    if state_path.exists():
        raise AssertionError(f"{label}: state file still exists — {state_path}")


def run_state_file_tests(bin_dir: str) -> None:
    """Run state-file assertions: install --all → verify state, uninstall --all → verify cleared."""
    extra_env = {"PATH": _bin_path(bin_dir)}

    # -- install --all → state file written --------------------------------
    print("=== Wizard Lifecycle: install --all state file")
    home = harness.sandbox_home()

    # Precondition: no state file
    _assert_state_file_missing(home, "pre-install")

    harness.run_in_sandbox(home, "ai-harness", "install", "--all", extra_env=extra_env)

    _assert_state_file(
        home,
        {"opencode", "claude", "copilot"},
        "post install --all",
    )
    print("  PASS: state file written with all three agents after install --all")

    # -- uninstall --all → state file deleted -------------------------------
    print("=== Wizard Lifecycle: uninstall --all state file")
    harness.run_in_sandbox(home, "ai-harness", "uninstall", "--all", extra_env=extra_env)

    _assert_state_file_missing(home, "post uninstall --all")
    print("  PASS: state file deleted after uninstall --all")

    print("=== Wizard Lifecycle: all state file assertions passed")


# ------------------------------------------------------------------ pytest ---
# The runner above is invoked via ``invoke`` (see e2e/tasks.py).  The
# ``test_*`` wrappers below let pytest discover and exercise the same
# assertions — useful for the TDD cycle evidence table and for CI where
# invoke may not be available.


def test_install_all_writes_state_file() -> None:
    """Pytest wrapper: install --all should write the state file."""
    import shutil

    home = harness.sandbox_home()
    bin_dir = harness.sandboxed_tool_install(str(REPO_ROOT))
    try:
        run_state_file_tests(bin_dir)
    finally:
        harness.sandboxed_tool_uninstall()
        # Cleanup the synthetic home early (atexit handles it anyway).
