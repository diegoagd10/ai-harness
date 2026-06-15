"""install / uninstall orchestration.

These are the top-level workflows the CLI calls. They walk a Config's
mappings, drive the ``ops`` primitives, and own the manifest write plus
the OpenCode-only generation step (``opencode.json`` + slash commands).

The split mirrors the Go install package: ``install`` produces a Report
plus a slice of manifest entries; ``uninstall`` removes everything the
manifest currently owns.
"""

from __future__ import annotations

from pathlib import Path

from ai_harness.install.config import Config
from ai_harness.install.harness import Harness
from ai_harness.install.install import install as install_run
from ai_harness.install.manifest import ManifestEntry, manifest_path, read_manifest
from ai_harness.install.ops import (
    ACTION_COPIED,
    ACTION_OVERWRITTEN,
)
from ai_harness.install.uninstall import uninstall as uninstall_run

# --- helpers -------------------------------------------------------------


def _seed_repo(root: Path) -> None:
    """Build a minimal ai-harness repo with files for every copy + generate path."""
    (root / "skills" / "example").mkdir(parents=True)
    (root / "skills" / "example" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
    (root / "prompts" / "sdd").mkdir(parents=True)
    (root / "prompts" / "sdd" / "sdd-orchestrator.md").write_text("# orchestrator\n", encoding="utf-8")
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
        encoding="utf-8",
    )


def _make_config(repo: Path, home: Path, harnesses: list[Harness] | None = None) -> Config:
    return Config(
        repo_dir=repo,
        claude_dir=home / ".claude",
        agents_dir=home / ".agents",
        copilot_dir=home / ".copilot",
        opencode_dir=home / ".config" / "opencode",
        harnesses=harnesses or [],
    )


# --- install end-to-end --------------------------------------------------


def test_install_copies_every_artifact_and_writes_manifest(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    # install() reads $HOME for {{HOME}} substitution; pin it to the test home.
    monkeypatch.setenv("HOME", str(home))

    report, entries, error = install_run(cfg)

    assert error is None
    # 10 copied files (2 agents + 2 claude + 2 copilot + 4 opencode) plus
    # 1 generated command + 1 generated opencode.json = 12 outcomes.
    assert len(report) == 12
    assert len(entries) == 12
    # Copies can be COPIED or OVERWRITTEN; generators emit a third verb.
    allowed = {ACTION_COPIED, ACTION_OVERWRITTEN, "generated"}
    assert all(e.action in allowed for e in report)

    # Spot-check the on-disk artifacts.
    assert (home / ".claude" / "CLAUDE.md").read_text(encoding="utf-8") == "# agents\n"
    assert (home / ".copilot" / "copilot-instructions.md").read_text(encoding="utf-8") == "# agents\n"
    assert (home / ".agents" / "skills" / "example" / "SKILL.md").read_text(encoding="utf-8") == "# skill\n"
    assert (home / ".config" / "opencode" / "plugins" / "model-variants.ts").read_text(
        encoding="utf-8"
    ) == "export {};\n"

    # Generated OpenCode artifacts land too.
    opencode_json = home / ".config" / "opencode" / "opencode.json"
    assert opencode_json.is_file()
    rendered = opencode_json.read_text(encoding="utf-8")
    assert "{{HOME}}" not in rendered
    assert str(home) in rendered
    cmd = home / ".config" / "opencode" / "commands" / "sdd-status.md"
    assert cmd.is_file()
    assert "agent: sdd-orchestrator" in cmd.read_text(encoding="utf-8")

    # Manifest is on disk and contains every file the installer owns.
    manifest = read_manifest(cfg.opencode_dir)
    assert manifest is not None
    owned = {entry.dest for entry in manifest.installed}
    assert (home / ".claude" / "CLAUDE.md") in {Path(p) for p in owned}


def test_install_claude_only_skips_opencode_and_copilot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home, harnesses=[Harness.CLAUDE])

    report, entries, error = install_run(cfg)

    assert error is None
    # 2 agents + 2 claude = 4. No opencode / copilot files.
    assert len(report) == 4
    assert len(entries) == 4
    assert (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".copilot" / "copilot-instructions.md").exists()
    assert not (home / ".config" / "opencode" / "opencode.json").exists()
    assert not (home / ".config" / "opencode" / "commands").exists()


def test_install_opencode_only_skips_claude_and_copilot(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home, harnesses=[Harness.OPENCODE])
    monkeypatch.setenv("HOME", str(home))

    report, entries, error = install_run(cfg)

    assert error is None
    # 2 agents + 4 opencode copies + 1 generated command + 1 generated
    # opencode.json = 8 outcomes.
    assert len(report) == 8
    assert len(entries) == 8
    assert (home / ".config" / "opencode" / "plugins" / "model-variants.ts").exists()
    assert (home / ".config" / "opencode" / "opencode.json").exists()
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".copilot" / "copilot-instructions.md").exists()


def test_install_merges_manifest_on_reinstall(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    monkeypatch.setenv("HOME", str(home))

    # First install touches everything (10 copies + 1 cmd + 1 json = 12).
    install_run(cfg)
    manifest = read_manifest(cfg.opencode_dir)
    assert manifest is not None
    first_count = len(manifest.installed)
    assert first_count == 12

    # Narrow reinstall: only claude. The manifest must still own the
    # previously-installed opencode artifacts so a later uninstall cleans them.
    narrow = _make_config(repo, home, harnesses=[Harness.CLAUDE])
    install_run(narrow)
    manifest = read_manifest(narrow.opencode_dir)
    assert manifest is not None
    assert len(manifest.installed) == first_count
    opencode_dest = str(home / ".config" / "opencode" / "plugins" / "model-variants.ts")
    assert any(entry.dest == opencode_dest for entry in manifest.installed)


def test_install_propagates_missing_source_error(tmp_path: Path) -> None:
    repo = tmp_path / "bare"
    home = tmp_path / "home"
    (repo / "skills").mkdir(parents=True)
    (repo / "AGENTS.md").write_text("# agents\n", encoding="utf-8")
    cfg = _make_config(repo, home)

    report, entries, error = install_run(cfg)

    assert error is not None
    # No files were copied because the very first mapping (skills) was
    # incomplete? Actually the first mapping IS the skills dir and it has
    # no contents, so the copy succeeds with zero files. But the prompts/sdd
    # source is missing → that's where the error fires. Either way, the
    # contract is "error is set, manifest is still written with the
    # artifacts that DID land before the failure".
    # For this fixture the skills copy succeeds but the prompts/sdd dir
    # is missing → error after partial work.
    assert isinstance(error, str)


# --- uninstall end-to-end ------------------------------------------------


def test_uninstall_removes_every_owned_file(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    monkeypatch.setenv("HOME", str(home))
    install_run(cfg)

    report, error = uninstall_run(cfg)

    assert error is None
    # 10 file copies (manifest-driven) + 1 generated command + 1 generated
    # opencode.json, all removed. The 2 generated entries appear ONCE in
    # the report (via the generator path), not via the manifest loop.
    assert len(report) == 12
    assert (home / ".claude" / "CLAUDE.md").exists() is False
    assert (home / ".config" / "opencode" / "opencode.json").exists() is False
    assert (home / ".config" / "opencode" / "commands" / "sdd-status.md").exists() is False
    assert not manifest_path(cfg.opencode_dir).exists()


def test_uninstall_preserves_unmanifested_user_files(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    monkeypatch.setenv("HOME", str(home))
    install_run(cfg)
    # Add a user file that was never installed.
    user_file = home / ".config" / "opencode" / "user.md"
    user_file.write_text("keep", encoding="utf-8")

    uninstall_run(cfg)

    assert user_file.read_text(encoding="utf-8") == "keep"


def test_uninstall_is_noop_without_manifest(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)

    report, error = uninstall_run(cfg)

    assert error is None
    assert report == []


def test_uninstall_narrow_selection_removes_only_that_harness(tmp_path: Path, monkeypatch) -> None:
    # The Python uninstall honors --harness differently from Go: a narrow
    # selection only removes that harness's files (Go cleans everything).
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    monkeypatch.setenv("HOME", str(home))
    install_run(cfg)

    narrow = _make_config(repo, home, harnesses=[Harness.CLAUDE])
    report, error = uninstall_run(narrow)

    assert error is None
    assert (home / ".claude" / "CLAUDE.md").exists() is False
    # opencode artifacts survive a narrow uninstall.
    assert (home / ".config" / "opencode" / "opencode.json").exists() is True
    assert (home / ".copilot" / "copilot-instructions.md").exists() is True


def test_uninstall_rejects_unsafe_manifest_atomically(tmp_path: Path) -> None:
    # Hand-craft a manifest with one safe + one unsafe entry; uninstall must
    # reject the unsafe one before deleting the safe one.
    from ai_harness.install.manifest import write_manifest

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    safe = home / ".config" / "opencode" / "AGENTS.md"
    safe.parent.mkdir(parents=True)
    safe.write_text("keep", encoding="utf-8")
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    write_manifest(
        cfg.opencode_dir,
        [
            ManifestEntry(dest=str(safe), kind="file"),
            ManifestEntry(dest=str(outside), kind="file"),
        ],
    )

    report, error = uninstall_run(cfg)

    assert error is not None
    # The safe file must not have been removed before the unsafe check.
    assert safe.read_text(encoding="utf-8") == "keep"
    assert outside.read_text(encoding="utf-8") == "keep"
    assert report == []


def test_uninstall_narrow_rejects_unsafe_entry_outside_selection(
    tmp_path: Path,
) -> None:
    """Narrow uninstall must validate the ENTIRE manifest, not just the
    entries belonging to the selected harness.

    Regression: ``uninstall()`` filtered manifest entries by selected
    harness first, then validated only the filtered subset.  A narrow
    uninstall could remove the selected harness's files even when the
    manifest contained an unsafe / tampered entry for another root or
    outside managed roots.  This violates fail-closed manifest safety.

    The fix: validate every manifest entry BEFORE narrowing the selection.
    """
    from ai_harness.install.manifest import write_manifest

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)

    # Hand-craft a manifest with:
    #   1. A safe entry inside a managed root (belongs to Claude).
    #   2. An unsafe entry outside ALL managed roots.
    safe_claude = home / ".claude" / "CLAUDE.md"
    safe_claude.parent.mkdir(parents=True)
    safe_claude.write_text("keep", encoding="utf-8")
    unsafe_outside = tmp_path / "outside.txt"
    unsafe_outside.write_text("danger", encoding="utf-8")

    write_manifest(
        cfg.opencode_dir,
        [
            ManifestEntry(dest=str(safe_claude), kind="file"),
            ManifestEntry(dest=str(unsafe_outside), kind="file"),
        ],
    )

    # Narrow uninstall: only Claude.  The unsafe entry sits outside the
    # Claude selection but the entire manifest must STILL be rejected.
    narrow = _make_config(repo, home, harnesses=[Harness.CLAUDE])
    report, error = uninstall_run(narrow)

    assert error is not None, (
        "uninstall must reject unsafe manifest atomically even for narrow selection"
    )
    # Atomicity: the safe Claude file must not have been removed before the
    # rejection.
    assert safe_claude.read_text(encoding="utf-8") == "keep"
    assert unsafe_outside.read_text(encoding="utf-8") == "danger"
    assert report == []


def test_uninstall_manifest_driven_no_repo_prompts(
    tmp_path: Path, monkeypatch
) -> None:
    """Uninstall succeeds when repo prompts/commands dir is missing.

    Regression: ``remove_commands`` used to read canonical command names
    from ``cfg.repo_dir/prompts/commands``, which raised
    ``FileNotFoundError`` when uninstall ran outside the repo.  Now the
    uninstall loop is manifest-driven — no repo is required.
    """
    import shutil

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    monkeypatch.setenv("HOME", str(home))
    install_run(cfg)

    # Remove the canonical prompts directory so the repo lacks commands.
    shutil.rmtree(repo / "prompts" / "commands")

    report, error = uninstall_run(cfg)

    assert error is None
    # All 12 entries (including the generated command + opencode.json)
    # are removed manifest-driven — no repo access needed.
    assert len(report) == 12
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".config" / "opencode" / "opencode.json").exists()
    # The command file still existed on disk and was removed.
    assert not (home / ".config" / "opencode" / "commands" / "sdd-status.md").exists()


# --- detect_installed_harnesses ------------------------------------------


def test_uninstall_narrow_preserves_shared_agents_when_other_harnesses_remain(
    tmp_path: Path, monkeypatch
) -> None:
    """Narrow uninstall must preserve .agents/ when other harnesses remain installed.

    Regression: _entries_for_harnesses unconditionally added cfg.agents_dir
    to selected roots for any narrow selection, removing shared .agents
    artifacts while OpenCode/Copilot were still installed.
    """
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    monkeypatch.setenv("HOME", str(home))
    install_run(cfg)

    # Uninstall only Claude — .agents must survive because OpenCode
    # and Copilot are still installed and depend on .agents/.
    narrow = _make_config(repo, home, harnesses=[Harness.CLAUDE])
    report, error = uninstall_run(narrow)

    assert error is None
    # Claude files gone.
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".claude" / "skills" / "example" / "SKILL.md").exists()
    # .agents files MUST survive (shared by remaining OpenCode/Copilot).
    assert (home / ".agents" / "skills" / "example" / "SKILL.md").exists(), (
        ".agents/skills must survive narrow uninstall when other harnesses remain"
    )
    assert (home / ".agents" / "AGENTS.md").exists(), (
        ".agents/AGENTS.md must survive narrow uninstall when other harnesses remain"
    )
    # Other harness files survive.
    assert (home / ".copilot" / "copilot-instructions.md").exists()
    assert (home / ".config" / "opencode" / "opencode.json").exists()


def test_uninstall_narrow_removes_agents_when_last_harness_uninstalled(
    tmp_path: Path,
) -> None:
    """Narrow uninstall must remove .agents/ when the selection covers all
    installed harnesses (no other harness remains with dependencies).
    """
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    # Install only Claude — the only harness with entries after install.
    cfg = _make_config(repo, home, harnesses=[Harness.CLAUDE])
    install_run(cfg)

    # Uninstall Claude (the sole installed harness) — .agents must be
    # removed too because no other harness remains.
    report, error = uninstall_run(cfg)

    assert error is None
    assert not (home / ".claude" / "CLAUDE.md").exists()
    assert not (home / ".claude" / "skills" / "example" / "SKILL.md").exists()
    # .agents files must be removed; no other harness depends on them.
    assert not (home / ".agents" / "skills" / "example" / "SKILL.md").exists(), (
        ".agents/skills must be removed when last harness is uninstalled"
    )
    assert not (home / ".agents" / "AGENTS.md").exists(), (
        ".agents/AGENTS.md must be removed when last harness is uninstalled"
    )


def test_detect_installed_harnesses_finds_all_when_manifest_has_them(
    tmp_path: Path, monkeypatch
) -> None:
    from ai_harness.install.uninstall import detect_installed_harnesses

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)
    monkeypatch.setenv("HOME", str(home))
    install_run(cfg)

    installed = detect_installed_harnesses(cfg)
    assert Harness.OPENCODE in installed
    assert Harness.CLAUDE in installed
    assert Harness.COPILOT in installed


def test_detect_installed_harnesses_empty_when_no_manifest(tmp_path: Path) -> None:
    from ai_harness.install.uninstall import detect_installed_harnesses

    repo = tmp_path / "repo"
    home = tmp_path / "home"
    _seed_repo(repo)
    cfg = _make_config(repo, home)

    assert detect_installed_harnesses(cfg) == []
