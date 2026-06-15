"""Config: where to install, what to install.

Carries every host-specific path the install/uninstall code needs. The
operations (``install``, ``uninstall``, ``generate_*``) take a ``Config``
explicitly so the logic stays pure and testable against temp dirs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_harness.install.harness import ALL_HARNESSES, Harness

# --- resolve_repo_dir -------------------------------------------------------


def test_resolve_repo_dir_picks_explicit_repo(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    resolved = _resolve(tmp_path, "/some/cwd")
    assert resolved == tmp_path


def test_resolve_repo_dir_falls_back_to_cwd(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    resolved = _resolve("", str(tmp_path))
    assert resolved == tmp_path


def test_resolve_repo_dir_rejects_repo_missing_markers(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="skills"):
        _resolve("", str(tmp_path))
    with pytest.raises(ValueError, match="AGENTS.md"):
        _resolve(str(tmp_path), "/cwd")


def test_resolve_repo_dir_names_both_missing_markers(tmp_path: Path) -> None:
    # A bare temp dir has neither marker; the error should mention both so
    # the user knows what to add.
    with pytest.raises(ValueError) as excinfo:
        _resolve("", str(tmp_path))
    message = str(excinfo.value)
    assert "skills" in message and "AGENTS.md" in message


# --- Config.wants -----------------------------------------------------------


def test_wants_empty_harnesses_includes_everything() -> None:
    cfg = _cfg(_tmp_repo())
    for harness in ALL_HARNESSES:
        assert cfg.wants(harness) is True


def test_wants_respects_selection() -> None:
    cfg = _cfg(_tmp_repo(), harnesses=[Harness.CLAUDE])
    assert cfg.wants(Harness.CLAUDE) is True
    assert cfg.wants(Harness.OPENCODE) is False
    assert cfg.wants(Harness.COPILOT) is False


# --- Config.mappings --------------------------------------------------------


def test_mappings_empty_selection_includes_all_targets() -> None:
    cfg = _cfg(_tmp_repo())
    dests = _dests(cfg)
    # .agents artifacts (always-on) and every selectable harness.
    for path in (
        cfg.agents_dir / "skills",
        cfg.agents_dir / "AGENTS.md",
        cfg.claude_dir / "skills",
        cfg.claude_dir / "CLAUDE.md",
        cfg.copilot_dir / "skills",
        cfg.copilot_dir / "copilot-instructions.md",
        cfg.opencode_dir / "skills",
        cfg.opencode_dir / "AGENTS.md",
        cfg.opencode_dir / "prompts" / "sdd",
        cfg.opencode_dir / "plugins",
    ):
        assert path in dests, f"missing target {path}"


def test_mappings_claude_only_omits_opencode_and_copilot() -> None:
    cfg = _cfg(_tmp_repo(), harnesses=[Harness.CLAUDE])
    dests = _dests(cfg)
    assert cfg.claude_dir / "CLAUDE.md" in dests
    assert cfg.agents_dir / "AGENTS.md" in dests
    assert cfg.opencode_dir / "plugins" not in dests
    assert cfg.copilot_dir / "copilot-instructions.md" not in dests


def test_mappings_opencode_only_omits_claude_and_copilot() -> None:
    cfg = _cfg(_tmp_repo(), harnesses=[Harness.OPENCODE])
    dests = _dests(cfg)
    assert cfg.opencode_dir / "plugins" in dests
    assert cfg.claude_dir / "CLAUDE.md" not in dests
    assert cfg.copilot_dir / "copilot-instructions.md" not in dests


def test_mappings_copilot_only_omits_claude_and_opencode() -> None:
    # Triangulation: a different single-harness selection must produce a
    # different dest set, so the want() filter is actually doing work.
    cfg = _cfg(_tmp_repo(), harnesses=[Harness.COPILOT])
    dests = _dests(cfg)
    assert cfg.copilot_dir / "copilot-instructions.md" in dests
    assert cfg.claude_dir / "CLAUDE.md" not in dests
    assert cfg.opencode_dir / "plugins" not in dests


def test_mappings_agents_artifacts_always_present() -> None:
    # The .agents artifacts are always copied regardless of selection; they
    # carry the persona / skills the other harnesses do not have a slot for.
    for selection in ([], [Harness.CLAUDE], [Harness.OPENCODE, Harness.COPILOT]):
        cfg = _cfg(_tmp_repo(), harnesses=selection)
        dests = _dests(cfg)
        assert cfg.agents_dir / "skills" in dests
        assert cfg.agents_dir / "AGENTS.md" in dests


# --- Config.owned_roots -----------------------------------------------------


def test_owned_roots_lists_every_managed_dir() -> None:
    cfg = _cfg(_tmp_repo())
    roots = set(cfg.owned_roots())
    assert cfg.claude_dir in roots
    assert cfg.agents_dir in roots
    assert cfg.copilot_dir in roots
    assert cfg.opencode_dir in roots
    # Manifest directory (sibling of opencode_dir) is also a managed root.
    assert cfg.opencode_dir.parent / "ai-harness" in roots


# --- helpers ---------------------------------------------------------------


def _seed_repo(root: Path) -> None:
    """Add the two markers ``ResolveRepoDir`` requires."""
    (root / "skills").mkdir(exist_ok=True)
    (root / "AGENTS.md").write_text("# agents\n", encoding="utf-8")


def _tmp_repo() -> Path:
    import tempfile

    root = Path(tempfile.mkdtemp())
    _seed_repo(root)
    return root


def _resolve(repo: str | Path, cwd: str | Path) -> Path:
    # Imported lazily so the test file fails closed when the module is missing.
    from ai_harness.install.config import resolve_repo_dir

    return resolve_repo_dir(str(repo) if repo else None, str(cwd) if cwd else None)


def _cfg(repo: Path, *, harnesses: list[Harness] | None = None) -> object:
    from ai_harness.install.config import Config

    return Config(
        repo_dir=repo,
        claude_dir=Path("/h") / ".claude",
        agents_dir=Path("/h") / ".agents",
        copilot_dir=Path("/h") / ".copilot",
        opencode_dir=Path("/h") / ".config" / "opencode",
        harnesses=harnesses or [],
    )


def _dests(cfg: object) -> set[Path]:
    return {dest for _src, dest in cfg.mappings()}
