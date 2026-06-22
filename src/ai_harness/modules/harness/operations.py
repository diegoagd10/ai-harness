"""Harness operations — core install/uninstall logic, no CLI.

Deep module: owns the path-mapping knowledge, the resource enumeration,
the idempotent writes, and the manifest persistence. The command layer
is a thin typer adapter that parses ``-o`` and delegates here.

The per-agent-CLI path mapping was simplified from a dual-source
layout to destination-only paths when unused targets were dropped;
see docs/adr/0001-collapse-agent-cli-paths.md for rationale.

Agent CLIs that support agents as a native concept (OpenCode) get the
loop agent templates rendered into their agent directory instead of the
persona+skills pair. Each CLI's render is handled by a provider-specific
function in ``renderers.py``.

Public surface (re-exported from the package)
---------------------------------------------
install_for_agent_clis     Map bundled resources to agent CLI paths, write, record manifest.
re_render_for_agent_clis   Re-write rendered loop agents without touching the install manifest.
uninstall_for_agent_clis   Remove files recorded in the manifest.
init_repo                  Scaffold CODING_STANDARDS.md skeleton and CLAUDE.md labels-policy block.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from functools import partial
from importlib.resources import files
from pathlib import Path

from ai_harness.modules.harness.labels import ensure_labels
from ai_harness.modules.harness.models import AgentCli, InitResult, InstallManifest
from ai_harness.modules.harness.renderers import render_agents

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


# --- install artifact writers ---------------------------------------------
#
# Each writer takes *home* and returns the absolute paths it wrote. Per-CLI
# destination knowledge lives in the writers' bound arguments (the persona
# writer) or in the render seam (the rendered-agents writer) — never in a
# CLI-keyed path table inside the install loop.


def _write_persona_and_skills(home: Path, *, config_dest_rel: str, tree_dest_rel: str) -> list[Path]:
    """Copy the persona file + skills tree into *home*; return absolute paths written."""
    resources = _resources_root()
    written: list[Path] = []

    config_dest = home / config_dest_rel
    config_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resources / _CONFIG_SOURCE, config_dest)
    written.append(config_dest)

    tree_dest = home / tree_dest_rel
    shutil.copytree(resources / _TREE_SOURCE, tree_dest, dirs_exist_ok=True)
    written.extend(_walk_files(tree_dest))

    return written


def _write_rendered_agents(home: Path, *, cli: AgentCli) -> list[Path]:
    """Render the loop agents for *cli* into *home*; return absolute paths written.

    Delegates override-store loading to ``render_agents`` (which reads
    ``~/.ai-harness/overrides.json`` itself), so a missing file is a no-op
    and a malformed file fails loudly — no pre-loading duplication here.
    """
    written: list[Path] = []
    for rel, content in render_agents(cli, home=home):
        dest = home / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        written.append(dest)
    return written


# --- data-driven install plan --------------------------------------------
#
# One table maps each agent CLI to its ordered list of artifact writers. The
# install loop dispatches purely through this table — adding a CLI is one entry.

_InstallWriter = Callable[[Path], list[Path]]

_INSTALL_PLAN: dict[AgentCli, list[_InstallWriter]] = {
    AgentCli.GENERIC: [
        partial(_write_persona_and_skills, config_dest_rel=".agents/AGENTS.md", tree_dest_rel=".agents/skills"),
    ],
    AgentCli.CLAUDE: [
        partial(_write_persona_and_skills, config_dest_rel=".claude/CLAUDE.md", tree_dest_rel=".claude/skills"),
        partial(_write_rendered_agents, cli=AgentCli.CLAUDE),
    ],
    AgentCli.COPILOT: [
        partial(
            _write_persona_and_skills,
            config_dest_rel=".github/copilot-instructions.md",
            tree_dest_rel=".copilot/skills",
        ),
        partial(_write_rendered_agents, cli=AgentCli.COPILOT),
    ],
    AgentCli.OPENCODE: [
        partial(_write_rendered_agents, cli=AgentCli.OPENCODE),
    ],
}

# Re-render plan — only writers that re-emit loop agents. Used by
# ``re_render_for_agent_clis`` for scoped refreshes (e.g. after the
# set-models wizard edits ``overrides.json``) where touching the install
# manifest would clobber other CLIs. CLIs with no native loop-agent
# concept (GENERIC) intentionally get an empty list.
_RENDER_PLAN: dict[AgentCli, list[_InstallWriter]] = {
    AgentCli.CLAUDE: [partial(_write_rendered_agents, cli=AgentCli.CLAUDE)],
    AgentCli.COPILOT: [partial(_write_rendered_agents, cli=AgentCli.COPILOT)],
    AgentCli.OPENCODE: [partial(_write_rendered_agents, cli=AgentCli.OPENCODE)],
}


# --- public operations ----------------------------------------------------


def install_for_agent_clis(agent_clis: list[AgentCli], *, home: Path | None = None) -> InstallManifest:
    """Map bundled resources to each agent CLI's native paths, write them
    idempotently (byte-identical reinstall), and record the manifest.

    Generic is always included in *agent_clis* — callers must prepend it.

    Each agent CLI's artifacts are described by ``_INSTALL_PLAN``: the persona
    file + skills tree, the rendered loop agents, or both. An agent CLI absent
    from the plan writes nothing.
    """
    home = home if home is not None else Path.home()

    written_paths: list[Path] = []
    files_by_agent_cli: dict[str, list[str]] = {}

    for agent_cli in agent_clis:
        agent_files: list[str] = []
        for write in _INSTALL_PLAN.get(agent_cli, []):
            written = write(home)
            written_paths.extend(written)
            agent_files.extend(_relative_to(home, p) for p in written)
        files_by_agent_cli[agent_cli.value] = agent_files

    manifest = InstallManifest(agent_clis=list(agent_clis), written_paths=written_paths)
    _write_manifest(home, list(agent_clis), files_by_agent_cli)
    return manifest


def re_render_for_agent_clis(agent_clis: list[AgentCli], *, home: Path | None = None) -> list[Path]:
    """Re-write the rendered loop agents for *agent_clis* without touching the install manifest.

    Use this for scoped refreshes — e.g. the ``set-models`` wizard editing
    ``overrides.json`` and re-emitting Claude's loop agents — where calling
    ``install_for_agent_clis`` with a single CLI would clobber the entries
    for other installed CLIs in ``~/.ai-harness/installed.json``.

    Behaviour:

    - Only writers in ``_RENDER_PLAN`` run: the persona+skills writers are
      install-time artifacts that do not depend on override state and are
      intentionally left alone. Re-running them would re-copy the static
      template tree and add nothing.
    - CLIs without native loop-agent support (GENERIC) are no-ops
      — they have an empty entry in ``_RENDER_PLAN``.
    - The install manifest is **never read or written**. The re-render path
      stays orthogonal to install bookkeeping; if a manifest exists, it is
      preserved verbatim.
    - Writes are idempotent: byte-identical content for unchanged overrides.

    Returns the absolute paths written (empty list when nothing changed).
    """
    home = home if home is not None else Path.home()

    written_paths: list[Path] = []
    for agent_cli in agent_clis:
        for write in _RENDER_PLAN.get(agent_cli, []):
            written = write(home)
            written_paths.extend(written)
    return written_paths


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


# --- repo-local scaffolding (init) ---------------------------------------

_CODING_STANDARDS_SKELETON = """\
# Coding Standards

## Style

## Testing

## Architecture

## Commits

## Quality gates
"""

_LABELS_POLICY_BLOCK = """\
<!-- ai-harness:start -->

## Loop label policy

- A **prd-issue** carries `ready-for-agent` only — never `loop`.
- A **sub-issue** carries `ready-for-agent` + `loop`.

<!-- ai-harness:end -->
"""

_AI_HARNESS_START = "<!-- ai-harness:start -->"
_AI_HARNESS_END = "<!-- ai-harness:end -->"


def init_repo(
    repo_root: Path | None = None,
) -> InitResult:
    """Scaffold repo-local artifacts at *repo_root*.

    Writes a titles-only ``CODING_STANDARDS.md`` if it does not exist, and
    appends a labels-policy block to ``CLAUDE.md`` if the file exists and the
    ``<!-- ai-harness:start -->`` / ``<!-- ai-harness:end -->`` markers are not
    already present. Creates the ``ready-for-agent`` and ``loop`` GitHub labels
    via ``gh label create`` (skips those that already exist).

    Idempotent by per-artifact detection — no sentinel file. Returns an
    ``InitResult`` describing which artifacts were written and which labels were
    created.

    *repo_root* defaults to the current working directory so tests can drive
    the operation against a temporary directory.
    """
    root = repo_root if repo_root is not None else Path.cwd()

    wrote_standards = _write_coding_standards(root)
    wrote_labels_policy, claude_md_missing = _write_labels_policy(root)
    label_result = ensure_labels(root)

    return InitResult(
        wrote_standards=wrote_standards,
        wrote_labels_policy=wrote_labels_policy,
        claude_md_missing=claude_md_missing,
        created_labels=label_result.created,
        label_warnings=label_result.warnings,
    )


def _write_coding_standards(root: Path) -> bool:
    """Write ``CODING_STANDARDS.md`` skeleton if absent; return whether written."""
    path = root / "CODING_STANDARDS.md"
    if path.exists():
        return False
    path.write_text(_CODING_STANDARDS_SKELETON, encoding="utf-8")
    return True


def _write_labels_policy(root: Path) -> tuple[bool, bool]:
    """Append labels-policy block to ``CLAUDE.md``.

    Returns ``(wrote, claude_md_missing)``:
    - ``(True, False)`` when the block was appended.
    - ``(False, False)`` when markers are already present (idempotent skip).
    - ``(False, True)`` when ``CLAUDE.md`` does not exist (silently skipped).
    """
    path = root / "CLAUDE.md"
    if not path.exists():
        return False, True

    content = path.read_text(encoding="utf-8")
    if _AI_HARNESS_START in content or _AI_HARNESS_END in content:
        return False, False

    if not content.endswith("\n"):
        content += "\n"
    content += "\n" + _LABELS_POLICY_BLOCK + "\n"
    path.write_text(content, encoding="utf-8")
    return True, False
