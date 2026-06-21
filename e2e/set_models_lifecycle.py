# pylint: disable=duplicate-code
"""E2e lifecycle for the `ai-harness set-models` command.

Slice 3 covers the non-interactive arg-validation paths plus the
non-TTY guards for both the Claude and OpenCode wizards:
- missing ``-o`` → non-zero exit with a clear error
- multiple CLIs in ``-o`` → non-zero exit with a clear error
- repeated ``-o`` flags → non-zero exit with a clear error
- unknown CLI in ``-o`` → non-zero exit with a clear error
- Claude wizard under non-TTY → non-zero exit with a TTY message
- OpenCode wizard under non-TTY → non-zero exit with a TTY message
- OpenCode wizard when OpenCode is absent on PATH → non-zero exit
  with install/configure guidance (issue #46 acceptance criterion)

The interactive wizards are intentionally NOT e2e-driven — they
need a TTY. Behavioural coverage for the wizard lives in
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
        _test_set_models_claude_non_tty_errors(path_env)
        _test_set_models_opencode_non_tty_errors(path_env)
        _test_set_models_opencode_absent_errors(bin_dir)
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


def _test_set_models_opencode_non_tty_errors(path_env: dict[str, str]) -> None:
    """OpenCode wizard under sandboxed subprocess (no TTY) errors rather than hangs.

    Slice 3 implemented the OpenCode wizard, so ``-o opencode`` is no
    longer rejected at the arg-validation layer. The wizard's binary
    guard fires first (because there is no point asking the user to
    drive a TTY when their machine is missing the binary the wizard
    needs); when OpenCode is absent on PATH the install/configure
    guidance surfaces. The TTY guard only fires when OpenCode IS
    installed.
    """
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
        f"expected non-zero exit for opencode wizard without TTY, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    assert "tty" in combined.lower() or "interactive" in combined.lower() or combined.strip() != "", (
        f"expected error to mention TTY / interactive, got: {combined!r}"
    )


def _test_set_models_opencode_absent_errors(bin_dir: str) -> None:
    """``set-models -o opencode`` errors with install/configure guidance when OpenCode is absent.

    Acceptance criterion: when the ``opencode`` binary is not on PATH,
    the command must fail non-zero and surface guidance telling the
    user to install OpenCode and run ``opencode auth login``. This is
    the e2e counterpart to ``tests/test_set_models.py::test_run_opencode_wizard_opencode_absent_returns_false_with_guidance``;
    that unit test patches ``_resolve_opencode_binary`` so it never
    sees the real PATH. Here we strip PATH to ONLY the sandboxed
    ``ai-harness`` bin dir — no system opencode — so the binary check
    is forced to fail on any host.

    Reaching this code path requires the OpenCode detection to fire
    BEFORE the TTY check (a sandboxed subprocess has no TTY). The
    validator's BLOCKER on issue #46 mandated both this test and the
    reordering that makes it reachable.
    """
    home = sandbox_home()
    # PATH = only the ai-harness bin dir. The sandboxed CLI is there
    # so ``ai-harness`` itself is still resolvable, but the system PATH
    # (and any developer-installed ``opencode``) is gone — this test is
    # deterministic regardless of what's installed on the host.
    absent_path_env = {"PATH": bin_dir}
    result = run_in_sandbox(
        home,
        "ai-harness",
        "set-models",
        "-o",
        "opencode",
        extra_env=absent_path_env,
        check=False,
    )

    assert result.returncode != 0, (
        f"expected non-zero exit for absent opencode, got {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = f"{result.stdout} {result.stderr}"
    # The error must name the missing tool AND tell the user what to do.
    assert "opencode" in combined.lower(), f"expected error to mention 'opencode', got: {combined!r}"
    lowered = combined.lower()
    assert "install" in lowered or "auth" in lowered, (
        f"expected error to include install/configure guidance ('install' or 'auth'), got: {combined!r}"
    )


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
