"""Harness operations — core install/uninstall logic, no CLI.

Deep module: owns the path-mapping knowledge, the resource enumeration,
the idempotent writes, and the manifest persistence. The command layer
is a thin typer adapter that parses ``-o`` and delegates here.

The per-agent-CLI path mapping was simplified from a dual-source
layout to destination-only paths when unused targets were dropped;
see docs/adr/0001-collapse-agent-cli-paths.md for rationale.

Public surface (re-exported from the package)
---------------------------------------------
install_for_agent_clis     Map bundled resources to agent CLI paths, write, record manifest.
uninstall_for_agent_clis   Remove files recorded in the manifest.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from ai_harness.modules.harness.models import AgentCli, InstallManifest

# --- the secret knowledge this module hides -------------------------------
#
# Every agent CLI installs the same two source artifacts — a persona file
# (AGENTS.md) and a skills tree (skills/) — into agent-CLI-specific
# destination paths under the user's home. The OPERATIONS module owns the
# mapping; callers state intent ("install claude") and never assemble
# paths, filenames, or directory layouts themselves.

_MANIFEST_DIR = ".ai-harness"
_MANIFEST_FILENAME = "installed.json"
_MANIFEST_VERSION = 1

_RESOURCE_PACKAGE = "ai_harness"
_RESOURCE_ROOT = "resources"

_CONFIG_SOURCE = "AGENTS.md"
_TREE_SOURCE = "skills"


@dataclass(frozen=True, slots=True)
class _AgentCliPaths:
    """Destination paths for one agent CLI's persona file and skills tree, relative to home.

    Only destinations are stored — source artifacts are identical across all agent CLIs.
    """

    config_dest: str  # e.g. ".claude/CLAUDE.md"
    tree_dest: str  # e.g. ".claude/skills"


_AGENT_CLI_PATHS: dict[AgentCli, _AgentCliPaths] = {
    AgentCli.GENERIC: _AgentCliPaths(
        config_dest=".agents/AGENTS.md",
        tree_dest=".agents/skills",
    ),
    AgentCli.CLAUDE: _AgentCliPaths(
        config_dest=".claude/CLAUDE.md",
        tree_dest=".claude/skills",
    ),
    AgentCli.COPILOT: _AgentCliPaths(
        config_dest=".github/copilot-instructions.md",
        tree_dest=".copilot/skills",
    ),
}


# --- resource access ------------------------------------------------------


def _resources_root() -> Path:
    """Resolve the bundled resources root as a concrete filesystem path."""
    return Path(str(files(_RESOURCE_PACKAGE))) / _RESOURCE_ROOT


# --- manifest persistence -------------------------------------------------


def _manifest_path(home: Path) -> Path:
    return home / _MANIFEST_DIR / _MANIFEST_FILENAME


def _write_manifest(home: Path, agent_clis: list[AgentCli], files_by_agent_cli: dict[str, list[str]]) -> None:
    data = {
        "version": _MANIFEST_VERSION,
        "agent_clis": [a.value for a in agent_clis],
        "files_by_agent_cli": files_by_agent_cli,
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
    non-empty dirs), so user files that happen to live alongside an agent CLI's
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


def install_for_agent_clis(agent_clis: list[AgentCli], *, home: Path | None = None) -> InstallManifest:
    """Map bundled resources to each agent CLI's native paths, write them
    idempotently (byte-identical reinstall), and record the manifest.

    Generic is always included in *agent_clis* — callers must prepend it.
    """
    home = home if home is not None else Path.home()
    resources = _resources_root()

    written_paths: list[Path] = []
    files_by_agent_cli: dict[str, list[str]] = {}

    config_src = resources / _CONFIG_SOURCE
    tree_src = resources / _TREE_SOURCE

    for agent_cli in agent_clis:
        paths = _AGENT_CLI_PATHS[agent_cli]

        config_dest = home / paths.config_dest
        config_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(config_src, config_dest)
        written_paths.append(config_dest)

        tree_dest = home / paths.tree_dest
        shutil.copytree(tree_src, tree_dest, dirs_exist_ok=True)
        tree_files = _walk_files(tree_dest)
        written_paths.extend(tree_files)

        rel_files = [_relative_to(home, config_dest), *(_relative_to(home, p) for p in tree_files)]
        files_by_agent_cli[agent_cli.value] = rel_files

    manifest = InstallManifest(agent_clis=list(agent_clis), written_paths=written_paths)
    _write_manifest(home, list(agent_clis), files_by_agent_cli)
    return manifest


def uninstall_for_agent_clis(agent_clis: list[AgentCli] | None, *, home: Path | None = None) -> None:
    """Remove files recorded in the manifest.

    *agent_clis* ``None`` → remove everything (no-args semantics).
    *agent_clis* list → remove only those agent CLIs; others survive.
    A missing manifest is a no-op (no prior install).
    """
    home = home if home is not None else Path.home()
    data = _read_manifest(home)
    if data is None:
        return

    files_by_agent_cli: dict[str, list[str]] = data.get("files_by_agent_cli", {})
    recorded_agent_clis = [AgentCli(a) for a in data.get("agent_clis", [])]

    to_remove = set(agent_clis) if agent_clis is not None else set(recorded_agent_clis)

    touched_dirs: set[Path] = set()
    for agent_cli in to_remove:
        for rel in files_by_agent_cli.get(agent_cli.value, []):
            path = home / rel
            path.unlink(missing_ok=True)
            touched_dirs.add(path.parent)

    _prune_empty_dirs(touched_dirs, home)

    remaining = [a for a in recorded_agent_clis if a not in to_remove]
    if not remaining:
        manifest_path = _manifest_path(home)
        manifest_path.unlink(missing_ok=True)
        _prune_empty_dirs({manifest_path.parent}, home)
    else:
        remaining_files = {a.value: files_by_agent_cli[a.value] for a in remaining if a.value in files_by_agent_cli}
        _write_manifest(home, remaining, remaining_files)
