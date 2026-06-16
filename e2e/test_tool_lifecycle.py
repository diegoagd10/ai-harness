"""Tool lifecycle (Lifecycle A): binary provisioning via uv tool install/uninstall.

Covers sandboxed ``uv tool install .``, ``--reinstall``, ``uninstall``, and
PATH assertions — all against isolated ``UV_TOOL_DIR`` / ``UV_TOOL_BIN_DIR``.
No product harness knowledge lives here.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import harness

REPO_ROOT = Path(__file__).resolve().parent.parent


def _assert_binary_on_path(bin_dir: str) -> None:
    """Verify ai-harness is found in the isolated bin directory."""
    found = shutil.which("ai-harness", path=bin_dir)
    if found is None:
        raise AssertionError(
            f"ai-harness not found on PATH after tool install (bin_dir={bin_dir})"
        )


def _assert_binary_not_on_path(bin_dir: str) -> None:
    """Verify ai-harness is NOT found in the isolated bin directory."""
    found = shutil.which("ai-harness", path=bin_dir)
    if found is not None:
        raise AssertionError(
            f"ai-harness still on PATH after tool uninstall "
            f"(bin_dir={bin_dir}, found={found})"
        )


def run() -> None:
    """Execute the full tool lifecycle (install → reinstall → uninstall)."""
    print("=== Tool Lifecycle: sandboxed uv tool install .")

    bin_dir = harness.sandboxed_tool_install(str(REPO_ROOT))
    _assert_binary_on_path(bin_dir)
    print("  PASS: ai-harness on PATH after fresh install")

    print("=== Tool Lifecycle: sandboxed uv tool install --reinstall .")
    bin_dir = harness.sandboxed_tool_reinstall(str(REPO_ROOT))
    _assert_binary_on_path(bin_dir)
    print("  PASS: ai-harness on PATH after reinstall")

    print("=== Tool Lifecycle: sandboxed uv tool uninstall ai-harness")
    harness.sandboxed_tool_uninstall()
    _assert_binary_not_on_path(bin_dir)
    print("  PASS: ai-harness removed from PATH after uninstall")

    print("=== Tool Lifecycle: all assertions passed")
