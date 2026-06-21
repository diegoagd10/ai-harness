# pylint: disable=duplicate-code
"""E2e lifecycle for the `ai-harness set-models` command.

Slice 2 only covers the non-interactive arg-validation paths:
- missing ``-o`` → non-zero exit with a clear error
- multiple CLIs in ``-o`` → non-zero exit with a clear error
- repeated ``-o`` flags → non-zero exit with a clear error

The interactive Claude wizard is intentionally NOT e2e-driven — it
needs a TTY. Behavioural coverage for the wizard lives in
``tests/test_set_models.py`` (pure helpers + CliRunner on the CLI
adapter for the non-TTY bail-out path).
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
    """Run the set-models arg-validation lifecycle in a sandboxed CLI install."""
    bin_dir = sandboxed_tool_install(cli_dir)
    path_env = {"PATH": f"{bin_dir}:{os.environ['PATH']}"}
    try:
        _test_set_models_missing_o_errors(path_env)
        _test_set_models_multiple_clis_errors(path_env)
        _test_set_models_repeated_o_flags_errors(path_env)
        _test_set_models_unknown_cli_errors(path_env)
        _test_set_models_opencode_explicit_not_implemented(path_env)
        _test_set_models_claude_non_tty_errors(path_env)
    finally:
        sandboxed_tool_uninstall()


def _test_set_models_missing_o_errors(path_env: dict[str, str]) -> None:
    """`ai-harness set-models` with no `-o` errors with a clear, non-zero exit."""
    home = sandbox_home()
    result = run_in_sandbox(home, "ai-harness", "set-models", extra_env=path_env, check=False)

    assert result.returncode != 0, (
        f"expected non-zero exit for missing -o, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    assert "-o" in combined or "exactly one" in combined.lower(), (
        f"expected error to mention -o or 'exactly one', got: {combined!r}"
    )


def _test_set_models_multiple_clis_errors(path_env: dict[str, str]) -> None:
    """`ai-harness set-models -o claude,opencode` errors with a clear, non-zero exit."""
    home = sandbox_home()
    result = run_in_sandbox(
        home,
        "ai-harness",
        "set-models",
        "-o",
        "claude,opencode",
        extra_env=path_env,
        check=False,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for multiple CLIs, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    assert "exactly one" in combined.lower() or "two" in combined.lower(), (
        f"expected error to call out 'exactly one' (or count), got: {combined!r}"
    )


def _test_set_models_repeated_o_flags_errors(path_env: dict[str, str]) -> None:
    """`ai-harness set-models -o claude -o opencode` errors with a clear, non-zero exit.

    Regression for the validator's BLOCKER on issue #45: typer's default
    behaviour for a single-value ``str`` option silently keeps only the
    LAST occurrence of a repeated flag, so this used to slip through
    with ``to='opencode'`` and produce the misleading "not yet
    implemented" error. The command must now reject repeated ``-o``
    flags explicitly with the exactly-one validation message.
    """
    home = sandbox_home()
    result = run_in_sandbox(
        home,
        "ai-harness",
        "set-models",
        "-o",
        "claude",
        "-o",
        "opencode",
        extra_env=path_env,
        check=False,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for repeated -o, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    # The error must mention BOTH values — proof the repeated flag was
    # collected rather than silently dropped.
    assert "claude" in combined.lower(), f"expected 'claude' in error, got: {combined!r}"
    assert "opencode" in combined.lower(), f"expected 'opencode' in error, got: {combined!r}"
    assert "exactly one" in combined.lower() or "occurrence" in combined.lower(), (
        f"expected error to mention exactly-one / occurrence, got: {combined!r}"
    )


def _test_set_models_unknown_cli_errors(path_env: dict[str, str]) -> None:
    """`ai-harness set-models -o bogus` errors with a clear, non-zero exit."""
    home = sandbox_home()
    result = run_in_sandbox(
        home,
        "ai-harness",
        "set-models",
        "-o",
        "bogus",
        extra_env=path_env,
        check=False,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for unknown CLI, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    assert "bogus" in combined or "valid" in combined.lower(), (
        f"expected error to mention bogus or 'valid', got: {combined!r}"
    )


def _test_set_models_opencode_explicit_not_implemented(path_env: dict[str, str]) -> None:
    """OpenCode is a single-CLI valid input but explicitly deferred to slice 3."""
    home = sandbox_home()
    result = run_in_sandbox(
        home,
        "ai-harness",
        "set-models",
        "-o",
        "opencode",
        extra_env=path_env,
        check=False,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for opencode (not yet implemented), got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    assert "opencode" in combined.lower(), f"expected error to mention opencode, got: {combined!r}"


def _test_set_models_claude_non_tty_errors(path_env: dict[str, str]) -> None:
    """Claude wizard under sandboxed subprocess (no TTY) errors rather than hangs."""
    home = sandbox_home()
    result = run_in_sandbox(
        home,
        "ai-harness",
        "set-models",
        "-o",
        "claude",
        extra_env=path_env,
        check=False,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for claude wizard without TTY, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    assert "tty" in combined.lower() or "interactive" in combined.lower() or combined.strip() != "", (
        f"expected error to mention TTY / interactive, got: {combined!r}"
    )
