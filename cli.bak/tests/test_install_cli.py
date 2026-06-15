"""Typer CLI surface tests for the install/uninstall commands.

The tests drive the CLI through ``CliRunner`` so they cover the same
dispatch path the real ``ai-harness`` script takes. The Typer surface is
narrow: the install / uninstall commands each accept ``--repo`` and
``--harness``; everything else is owned by the ``install`` Python package.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer
from rich.console import Console
from typer.testing import CliRunner

from ai_harness import compat
from ai_harness.cli import app

runner = CliRunner()


# --- shared fake-repo builder --------------------------------------------


def _fake_repo(root: Path) -> Path:
    """Build a minimal ai-harness repo inside ``root`` and return the path."""
    (root / "skills" / "example").mkdir(parents=True)
    (root / "skills" / "example" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
    (root / "prompts" / "sdd").mkdir(parents=True)
    (root / "prompts" / "sdd" / "sdd-orchestrator.md").write_text(
        "# orchestrator\n", encoding="utf-8"
    )
    (root / "agent-clis" / "opencode" / "plugins").mkdir(parents=True)
    (root / "agent-clis" / "opencode" / "plugins" / "model-variants.ts").write_text(
        "export {};\n", encoding="utf-8"
    )
    (root / "agent-clis" / "opencode" / "opencode.json").write_text(
        '{"prompt":"{file:{{HOME}}/prompts/x.md}"}', encoding="utf-8"
    )
    (root / "prompts" / "commands").mkdir(parents=True)
    (root / "prompts" / "commands" / "sdd-status.md").write_text(
        "---\ndescription: Show status\nsubtask: false\n---\nStatus: {{ARGS}}\n",
        encoding="utf-8"
    )
    return root


def _home_env(monkeypatch: pytest.MonkeyPatch, home: Path) -> None:
    monkeypatch.setenv("HOME", str(home))


# --- install: success path -----------------------------------------------


def test_install_command_copies_to_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _fake_repo(tmp_path / "repo")
    home = tmp_path / "home"
    _home_env(monkeypatch, home)
    result = runner.invoke(
        app,
        ["install", "--harness", "claude", "--repo", str(repo)],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    # claude + agents files exist
    assert (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == "# agents\n"
    assert (home / ".agents" / "skills" / "example" / "SKILL.md").read_text(
        encoding="utf-8"
    ) == "# skill\n"
    # claude-only must NOT touch opencode
    assert not (home / ".config" / "opencode" / "opencode.json").exists()
    # Manifest lives at the documented path
    assert (home / ".config" / "ai-harness" / "install-manifest.json").exists()


def test_install_command_opencode_generates_extras(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fake_repo(tmp_path / "repo")
    home = tmp_path / "home"
    _home_env(monkeypatch, home)
    result = runner.invoke(
        app,
        ["install", "--harness", "opencode", "--repo", str(repo)],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (home / ".config" / "opencode" / "opencode.json").is_file()
    assert (home / ".config" / "opencode" / "commands" / "sdd-status.md").is_file()
    assert not (home / ".claude" / "CLAUDE.md").exists()


def test_install_command_unknown_harness_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fake_repo(tmp_path / "repo")
    _home_env(monkeypatch, tmp_path / "home")
    result = runner.invoke(
        app,
        ["install", "--harness", "bogus", "--repo", str(repo)],
    )
    assert result.exit_code != 0
    assert "bogus" in result.stderr or "bogus" in result.stdout


def test_install_command_invalid_repo_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    _home_env(monkeypatch, tmp_path / "home")
    result = runner.invoke(
        app,
        ["install", "--harness", "claude", "--repo", str(bare)],
    )
    assert result.exit_code != 0


# --- uninstall: success path ---------------------------------------------


def test_uninstall_command_removes_owned_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fake_repo(tmp_path / "repo")
    home = tmp_path / "home"
    _home_env(monkeypatch, home)
    # Install first.
    install_result = runner.invoke(
        app,
        ["install", "--harness", "claude,opencode", "--repo", str(repo)],
    )
    assert install_result.exit_code == 0, install_result.stdout + install_result.stderr

    # Now uninstall everything.
    result = runner.invoke(app, ["uninstall", "--repo", str(repo)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".config" / "opencode" / "opencode.json").exists()
    assert not (home / ".config" / "opencode" / "commands" / "sdd-status.md").exists()


def test_uninstall_command_is_noop_without_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fake_repo(tmp_path / "repo")
    _home_env(monkeypatch, tmp_path / "home")
    result = runner.invoke(app, ["uninstall", "--repo", str(repo)])
    assert result.exit_code == 0, result.stdout + result.stderr
    # No error message; nothing to remove.
    assert "missing" not in (result.stderr or "").lower()


def test_uninstall_command_preserves_user_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _fake_repo(tmp_path / "repo")
    home = tmp_path / "home"
    _home_env(monkeypatch, home)
    install = runner.invoke(
        app, ["install", "--harness", "claude", "--repo", str(repo)]
    )
    assert install.exit_code == 0
    user = home / ".config" / "opencode" / "user.md"
    user.parent.mkdir(parents=True, exist_ok=True)
    user.write_text("keep me", encoding="utf-8")

    result = runner.invoke(app, ["uninstall", "--harness", "claude", "--repo", str(repo)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert user.read_text(encoding="utf-8") == "keep me"


# --- existing sdd commands still work ------------------------------------


def test_sdd_status_unchanged(tmp_path: Path) -> None:
    """Sanity: adding install/uninstall must not break sdd-status."""
    result = runner.invoke(app, ["sdd-status", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["schemaName"] == "ai-harness.sdd-status"


def test_sdd_continue_unchanged(tmp_path: Path) -> None:
    """Sanity: adding install/uninstall must not break sdd-continue."""
    result = runner.invoke(app, ["sdd-continue", "--json", "--cwd", str(tmp_path)])
    assert result.exit_code == 0


# --- regression: explicit empty --harness must fail -------------------


def test_install_empty_harness_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install --harness ""`` must fail, not install every harness."""
    repo = _fake_repo(tmp_path / "repo")
    _home_env(monkeypatch, tmp_path / "home")
    result = runner.invoke(
        app,
        ["install", "--harness", "", "--repo", str(repo)],
    )
    assert result.exit_code != 0


def test_install_whitespace_harness_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``install --harness "  "`` must fail, not install every harness."""
    repo = _fake_repo(tmp_path / "repo")
    _home_env(monkeypatch, tmp_path / "home")
    result = runner.invoke(
        app,
        ["install", "--harness", "  ", "--repo", str(repo)],
    )
    assert result.exit_code != 0


def test_uninstall_empty_harness_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``uninstall --harness ""`` must fail, not uninstall every harness."""
    repo = _fake_repo(tmp_path / "repo")
    home = tmp_path / "home"
    _home_env(monkeypatch, home)
    # Seed a manifest so uninstall has something it *could* remove.
    runner.invoke(
        app, ["install", "--harness", "claude", "--repo", str(repo)]
    )
    result = runner.invoke(
        app,
        ["uninstall", "--harness", "", "--repo", str(repo)],
    )
    assert result.exit_code != 0
    # The manifest-owned file must still exist (nothing was uninstalled).
    assert (home / ".claude" / "CLAUDE.md").exists()


def test_unknown_command_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["bogus"])
    assert result.exit_code == 2


# --- regression: picker RuntimeError handling in _resolve_selection -----


def test_resolve_selection_uninstall_fails_closed_on_picker_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """_resolve_selection must exit hard when the picker fails on uninstall.

    When *fail_on_picker_error* is True (the uninstall path), a
    RuntimeError from ``prompt_harnesses`` must result in a non-zero
    ``typer.Exit`` instead of silently falling back to ALL_HARNESSES.
    The fallback is safe for install but destructive for uninstall.
    """
    import sys as _sys
    import ai_harness.picker as _picker_mod
    from io import StringIO

    from ai_harness.cli import _resolve_selection

    monkeypatch.setattr(_sys.stdin, "isatty", lambda: True)

    def _failing_prompt(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("POSIX-raw-mode unavailable")

    monkeypatch.setattr(_picker_mod, "prompt_harnesses", _failing_prompt)

    console = Console(file=StringIO(), force_terminal=False)

    with pytest.raises(typer.Exit) as exc_info:
        _resolve_selection(
            None,
            console=console,
            title="Select harnesses to uninstall",
            fail_on_picker_error=True,
        )
    assert exc_info.value.exit_code == compat.EXIT_ERROR, (
        f"Expected exit code {compat.EXIT_ERROR}, got {exc_info.value.exit_code}"
    )
    # The error message must be printed to stderr advising --harness
    captured = capsys.readouterr()
    assert "picker unavailable" in captured.err.lower(), (
        f"Expected picker-unavailable message, got err: {captured.err!r}"
    )
    assert "--harness" in captured.err, (
        f"Expected --harness hint, got err: {captured.err!r}"
    )


def test_resolve_selection_install_falls_back_on_picker_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """_resolve_selection must fall back to all harnesses on install picker failure.

    The existing Go-backcompat behaviour: when POSIX raw mode is
    unavailable on a TTY, omitting ``--harness`` installs every harness.
    This test locks in the install fallback.
    """
    import sys as _sys
    import ai_harness.picker as _picker_mod
    from io import StringIO

    from ai_harness.cli import _resolve_selection
    from ai_harness.install.harness import ALL_HARNESSES

    monkeypatch.setattr(_sys.stdin, "isatty", lambda: True)

    def _failing_prompt(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("POSIX-raw-mode unavailable")

    monkeypatch.setattr(_picker_mod, "prompt_harnesses", _failing_prompt)

    console = Console(file=StringIO(), force_terminal=False)

    result = _resolve_selection(
        None,
        console=console,
        title="Select harnesses to install",
        fail_on_picker_error=False,
    )
    assert result.harnesses == list(ALL_HARNESSES), (
        f"Expected all harnesses, got {result.harnesses}"
    )
    # The fallback warning must be printed to stderr
    captured = capsys.readouterr()
    assert "installing every harness" in captured.err, (
        f"Expected fallback warning, got err: {captured.err!r}"
    )


def test_uninstall_no_tty_still_defaults_to_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-TTY uninstall without --harness must still return ALL_HARNESSES.

    This codepath (CI / scripts) is the safe default: the uninstall
    reads the manifest and only removes what was tracked, so "all"
    in this context is not destructive.  The dangerous path was the
    TTY picker RuntimeError fallback, which is now guarded by
    ``fail_on_picker_error``.
    """
    import sys as _sys
    from io import StringIO

    from ai_harness.cli import _resolve_selection
    from ai_harness.install.harness import ALL_HARNESSES

    monkeypatch.setattr(_sys.stdin, "isatty", lambda: False)

    console = Console(file=StringIO(), force_terminal=False)

    result = _resolve_selection(
        None,
        console=console,
        title="Select harnesses to uninstall",
        fail_on_picker_error=True,
    )
    assert result.harnesses == list(ALL_HARNESSES), (
        f"Non-TTY should default to all, got {result.harnesses}"
    )
