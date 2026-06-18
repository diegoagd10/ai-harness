"""Harness operations — core install/uninstall logic, no CLI.

Deep module: owns the path-mapping knowledge, the resource enumeration,
the idempotent writes, and the manifest persistence. The command layer
is a thin typer adapter that parses ``-o`` and delegates here.

Public surface (re-exported from the package)
---------------------------------------------
install_targets     Map bundled resources to target paths, write, record manifest.
uninstall_targets   Remove files recorded in the manifest.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from ai_harness.modules.harness.models import InstallManifest, Target

# --- the secret knowledge this module hides -------------------------------
#
# Each target's persona file and skills live at target-specific locations
# relative to the user's home. The persona source (resources/AGENTS.md) is
# copied with a per-target rename; the skills tree is copied verbatim.
# Concentrating this map here means callers state intent ("install claude")
# and never assemble paths, filenames, or directory layout themselves.

_MANIFEST_DIR = ".ai-harness"
_MANIFEST_FILENAME = "installed.json"
_MANIFEST_VERSION = 1

_RESOURCE_PACKAGE = "ai_harness"
_RESOURCE_ROOT = "resources"
_PERSONA_SOURCE = "AGENTS.md"
_SKILLS_SOURCE_DIR = "skills"


@dataclass(frozen=True, slots=True)
class _TargetLayout:
    """Where one target's persona file and skills tree live, relative to home."""

    persona_path: str  # e.g. ".claude/CLAUDE.md"
    skills_dir: str  # e.g. ".claude/skills"


_TARGET_LAYOUTS: dict[Target, _TargetLayout] = {
    Target.GENERIC: _TargetLayout(".agents/AGENTS.md", ".agents/skills"),
    Target.CLAUDE: _TargetLayout(".claude/CLAUDE.md", ".claude/skills"),
    Target.COPILOT: _TargetLayout(".github/copilot-instructions.md", ".copilot/skills"),
}


# --- resource access ------------------------------------------------------


def _resources_root() -> Path:
    """Resolve the bundled resources root as a concrete filesystem path."""
    return Path(str(files(_RESOURCE_PACKAGE))) / _RESOURCE_ROOT


# --- manifest persistence -------------------------------------------------


def _manifest_path(home: Path) -> Path:
    return home / _MANIFEST_DIR / _MANIFEST_FILENAME


def _write_manifest(home: Path, targets: list[Target], files_by_target: dict[str, list[str]]) -> None:
    data = {
        "version": _MANIFEST_VERSION,
        "targets": [t.value for t in targets],
        "files_by_target": files_by_target,
    }
    path = _manifest_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_manifest(home: Path) -> dict | None:
    path = _manifest_path(home)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# --- small path helpers ---------------------------------------------------


def _walk_files(root: Path) -> list[Path]:
    """All regular files under *root*, sorted for deterministic output."""
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix())


def _relative_to(home: Path, path: Path) -> str:
    """A path expressed relative to *home* as a POSIX string (portable on disk)."""
    return path.relative_to(home).as_posix()


def _prune_empty_dirs(dirs: set[Path], stop_at: Path) -> None:
    """Remove now-empty directories created by install, never touching *stop_at*.

    Only directories that are actually empty are removed (``rmdir`` refuses
    non-empty dirs), so user files that happen to live alongside a target's
    directory (e.g. an existing ~/.github/) are preserved.
    """
    candidates: set[Path] = set()
    for start in dirs:
        if start == stop_at:
            continue
        candidates.add(start)
        for ancestor in start.parents:
            if ancestor == stop_at:
                break
            candidates.add(ancestor)
    for candidate in sorted(candidates, key=lambda p: len(p.parts), reverse=True):
        try:
            candidate.rmdir()
        except OSError:
            # not empty, missing, or not a directory — leave it alone
            pass


# --- public operations ----------------------------------------------------


def install_targets(targets: list[Target], *, home: Path | None = None) -> InstallManifest:
    """Map bundled resources to each target's native paths, write them
    idempotently (byte-identical reinstall), and record the manifest.

    Generic is always included in *targets* — callers must prepend it.
    """
    home = home if home is not None else Path.home()
    resources = _resources_root()
    persona_src = resources / _PERSONA_SOURCE
    skills_src = resources / _SKILLS_SOURCE_DIR

    written_paths: list[Path] = []
    files_by_target: dict[str, list[str]] = {}

    for target in targets:
        layout = _TARGET_LAYOUTS[target]

        persona_dest = home / layout.persona_path
        persona_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(persona_src, persona_dest)
        written_paths.append(persona_dest)

        skills_dest = home / layout.skills_dir
        shutil.copytree(skills_src, skills_dest, dirs_exist_ok=True)
        skill_files = _walk_files(skills_dest)
        written_paths.extend(skill_files)

        rel_files = [_relative_to(home, persona_dest), *(_relative_to(home, p) for p in skill_files)]
        files_by_target[target.value] = rel_files

    manifest = InstallManifest(targets=list(targets), written_paths=written_paths)
    _write_manifest(home, list(targets), files_by_target)
    return manifest


def uninstall_targets(targets: list[Target] | None, *, home: Path | None = None) -> None:
    """Remove files recorded in the manifest.

    *targets* ``None`` → remove everything (no-args semantics).
    *targets* list → remove only those targets; others survive.
    A missing manifest is a no-op (no prior install).
    """
    home = home if home is not None else Path.home()
    data = _read_manifest(home)
    if data is None:
        return

    files_by_target: dict[str, list[str]] = data.get("files_by_target", {})
    recorded_targets = [Target(t) for t in data.get("targets", [])]

    to_remove = set(targets) if targets is not None else set(recorded_targets)

    touched_dirs: set[Path] = set()
    for target in to_remove:
        for rel in files_by_target.get(target.value, []):
            path = home / rel
            path.unlink(missing_ok=True)
            touched_dirs.add(path.parent)

    _prune_empty_dirs(touched_dirs, home)

    remaining = [t for t in recorded_targets if t not in to_remove]
    if not remaining:
        manifest_path = _manifest_path(home)
        manifest_path.unlink(missing_ok=True)
        _prune_empty_dirs({manifest_path.parent}, home)
    else:
        remaining_files = {t.value: files_by_target[t.value] for t in remaining if t.value in files_by_target}
        _write_manifest(home, remaining, remaining_files)
