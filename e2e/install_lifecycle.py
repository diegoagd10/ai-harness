"""E2e lifecycle for the `ai-harness install` command.

Provisions the CLI via `uv tool install` into an isolated sandbox, runs
`ai-harness install`, and asserts the expected stdout.
"""

from __future__ import annotations

import os

from e2e.harness import (
    run_in_sandbox,
    sandbox_home,
    sandboxed_tool_install,
    sandboxed_tool_uninstall,
)


def run(cli_dir: str) -> None:
    """Install the CLI in a sandbox and assert `ai-harness install` output."""
    home = sandbox_home()
    bin_dir = sandboxed_tool_install(cli_dir)
    try:
        result = run_in_sandbox(
            home,
            "ai-harness",
            "install",
            extra_env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )
        actual = result.stdout.strip()
        expected = "Hellow Muppet"
        if actual != expected:
            raise AssertionError(f"install output mismatch\n  expected: {expected!r}\n  actual:   {actual!r}")
    finally:
        sandboxed_tool_uninstall()
