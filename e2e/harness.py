"""Deep sandbox module for the e2e test suite.

Hides synthetic HOME lifecycle, isolated uv tool directories, subprocess
invocation, file assertions, and OpenSpec workspace seeding behind a small
interface. Lifecycle-specific knowledge lives in the lifecycle test files —
this module owns only the shared infrastructure.

Public surface
--------------
sandbox_home()          Create synthetic HOME; cleans up via atexit.
workspace_root()        Create temp workspace dir; cleans up via atexit.
sandboxed_tool_install  uv tool install into isolated UV_TOOL_DIR/UV_TOOL_BIN_DIR.
sandboxed_tool_reinstall uv tool install --reinstall into same isolated dirs.
sandboxed_tool_uninstall Remove isolated tool installation + cleanup.
run_in_sandbox          Execute a subprocess with HOME= and optional extra env.
assert_file_content     Compare actual file content against expected.
assert_file_missing     Assert that a path does NOT exist.
assert_file_exists      Assert that a path exists.
seed_openspec_change    Create a minimal ready change tree under a workspace root.
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# ------- internal state (hidden from callers) --------------------------------

_SANDBOXES: list[str] = []
_UV_TOOL_DIR: str | None = None


def _cleanup() -> None:
    """atexit handler: remove all synthetic directories."""
    for path in _SANDBOXES:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


atexit.register(_cleanup)


# ------- public interface ---------------------------------------------------


def sandbox_home() -> str:
    """Create a synthetic HOME directory; it is removed via atexit."""
    path = tempfile.mkdtemp(prefix="e2e-home-")
    _SANDBOXES.append(path)
    return path


def workspace_root() -> str:
    """Create a temp workspace directory registered for atexit cleanup.

    Returns an absolute path to a directory suitable for seeding OpenSpec
    change trees. The directory is tracked in ``_SANDBOXES`` and will be
    removed by the atexit handler alongside synthetic HOME and uv-tool dirs.
    """
    path = tempfile.mkdtemp(prefix="e2e-sdd-ws-")
    _SANDBOXES.append(path)
    return path


def sandboxed_tool_install(cli_dir: str) -> str:
    """Install ai-harness via ``uv tool install`` into isolated dirs.

    Sets ``UV_TOOL_DIR`` and ``UV_TOOL_BIN_DIR`` to temporary directories so
    the developer's real uv tool registry and PATH are never touched.

    Returns the bin directory prefix (absolute path) containing ``ai-harness``.
    """
    global _UV_TOOL_DIR
    _UV_TOOL_DIR = tempfile.mkdtemp(prefix="e2e-uv-tools-")
    _SANDBOXES.append(_UV_TOOL_DIR)
    uv_bin_dir = os.path.join(_UV_TOOL_DIR, "bin")
    os.makedirs(uv_bin_dir, exist_ok=True)

    env = os.environ.copy()
    env["UV_TOOL_DIR"] = _UV_TOOL_DIR
    env["UV_TOOL_BIN_DIR"] = uv_bin_dir

    subprocess.run(
        ["uv", "tool", "install", cli_dir],
        env=env,
        check=True,
    )
    return uv_bin_dir


def sandboxed_tool_uninstall() -> None:
    """Remove the isolated tool installation."""
    if _UV_TOOL_DIR is None or not os.path.isdir(_UV_TOOL_DIR):
        return
    uv_bin_dir = os.path.join(_UV_TOOL_DIR, "bin")
    env = os.environ.copy()
    env["UV_TOOL_DIR"] = _UV_TOOL_DIR
    env["UV_TOOL_BIN_DIR"] = uv_bin_dir
    subprocess.run(
        ["uv", "tool", "uninstall", "ai-harness"],
        env=env,
        check=True,
    )


def sandboxed_tool_reinstall(cli_dir: str) -> str:
    """Reinstall ai-harness into the existing isolated uv tool dirs."""
    if _UV_TOOL_DIR is None or not os.path.isdir(_UV_TOOL_DIR):
        raise RuntimeError("sandboxed_tool_install() must run before reinstall")
    uv_bin_dir = os.path.join(_UV_TOOL_DIR, "bin")
    os.makedirs(uv_bin_dir, exist_ok=True)

    env = os.environ.copy()
    env["UV_TOOL_DIR"] = _UV_TOOL_DIR
    env["UV_TOOL_BIN_DIR"] = uv_bin_dir

    subprocess.run(
        ["uv", "tool", "install", "--reinstall", cli_dir],
        env=env,
        check=True,
    )
    return uv_bin_dir


def run_in_sandbox(
    home: str,
    *args: str,
    extra_env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Execute a subprocess with ``HOME=home``.

    The caller may pass ``extra_env`` to layer additional variables on top of
    a copy of ``os.environ`` (e.g. PATH adjustments).
    """
    env = os.environ.copy()
    env["HOME"] = home
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        list(args),
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


# ------- file assertions ----------------------------------------------------


def assert_file_content(actual: Path, expected: Path, label: str) -> None:
    """Assert *actual* content matches *expected*; raise on mismatch."""
    if not actual.is_file():
        raise AssertionError(f"{label}: missing — {actual}")
    actual_text = actual.read_text(encoding="utf-8")
    expected_text = expected.read_text(encoding="utf-8")
    if actual_text != expected_text:
        raise AssertionError(f"{label}: content mismatch\n  actual:   {actual}\n  expected: {expected}")


def assert_file_missing(path: Path, label: str) -> None:
    """Assert *path* does NOT exist; raise otherwise."""
    if path.exists():
        raise AssertionError(f"{label}: still exists — {path}")


def assert_file_exists(path: Path, label: str) -> None:
    """Assert *path* exists; raise otherwise."""
    if not path.exists():
        raise AssertionError(f"{label}: missing — {path}")


# ------- workspace seeding --------------------------------------------------


def seed_openspec_change(root: Path, name: str, tasks_md: str) -> Path:
    """Create a minimal ready OpenSpec change tree under *root*.

    Returns the change root directory (``root/openspec/changes/<name>``).
    """
    change_root = root / "openspec" / "changes" / name
    _write_file(change_root / "proposal.md", "# Proposal\n")
    _write_file(change_root / "specs" / "auth" / "spec.md", "# Auth Spec\n")
    _write_file(change_root / "design.md", "# Design\n")
    _write_file(change_root / "tasks.md", tasks_md)
    return change_root


def _write_file(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
