"""Harness operations — core install/uninstall logic, no CLI.

Deep module: owns the path-mapping knowledge, the resource enumeration,
the idempotent writes, and the manifest persistence. The command layer
is a thin typer adapter that parses ``-o`` and delegates here.

The per-agent-CLI path mapping was simplified from a dual-source
layout to destination-only paths when unused targets were dropped;
see docs/adr/0001-collapse-agent-cli-paths.md for rationale.

Agent CLIs that support agents as a native concept (OpenCode) get the
change agent templates rendered into their agent directory instead of the
persona+skills pair. Each CLI's render is handled by a provider-specific
function in ``renderers.py``.

Public surface (re-exported from the package)
---------------------------------------------
InstallManifest            The exact record uninstall_for_agent_clis consumes.
InitResult                 Observable outcome of init_repo.
install_for_agent_clis     Map bundled resources to agent CLI paths, write, record manifest.
re_render_for_agent_clis   Re-write rendered change agents without touching the install manifest.
uninstall_for_agent_clis   Remove files recorded in the manifest.
init_repo                  Scaffold CODING_STANDARDS.md and the agent-doc init block.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from importlib.resources import files
from pathlib import Path

from ai_harness.modules.harness.models import AgentCli
from ai_harness.modules.harness.renderers import render_agents

__all__ = [
    "InitResult",
    "InstallManifest",
    "init_repo",
    "install_for_agent_clis",
    "re_render_for_agent_clis",
    "uninstall_for_agent_clis",
]

# --- constants --------------------------------------------------------------
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


_CODING_STANDARDS_SKELETON = """\
# Coding Standards

## Style

## Testing

## Architecture

## Commits

## Quality gates
"""

# New init markers — the managed block identity. Replaces the pre-refactor
# generic `ai-harness:start/end` markers so the block's owner is unambiguous
# at a glance.
_AI_HARNESS_INIT_START = "<!-- ai-harness:init:start -->"
_AI_HARNESS_INIT_END = "<!-- ai-harness:init:end -->"

# Legacy markers — kept as private constants for the legacy-detection
# branch in `_apply_init_block` / `_migrate_legacy_block`. Never re-exported;
# never appear in any user-facing string post-refactor.
_AI_HARNESS_START = "<!-- ai-harness:start -->"
_AI_HARNESS_END = "<!-- ai-harness:end -->"

_INIT_BLOCK = f"""\
{_AI_HARNESS_INIT_START}

Follow the repo's `CODING_STANDARDS.md`.

{_AI_HARNESS_INIT_END}
"""

# Agent docs that receive the init block, in deterministic write order.
# CLAUDE.md is Claude Code's persona; AGENTS.md is the OpenCode/generic persona.
# Post-refactor both files are *always* created when absent — a clean repo
# receives both rather than zero.
_INIT_BLOCK_DOCS = ("CLAUDE.md", "AGENTS.md")


# --- public types -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InstallManifest:
    """The exact record ``uninstall_for_agent_clis`` consumes.

    Persisted to ``~/.ai-harness/installed.json``.
    """

    agent_clis: list[AgentCli]
    written_paths: list[Path]


@dataclass(frozen=True, slots=True)
class InitResult:
    """Observable outcome of ``init_repo``.

    Each field reports whether the corresponding artifact was written.
    ``wrote_init_block`` is ``True`` when at least one agent doc was
    freshly written, appended, or migrated; ``init_block_targets`` lists
    every agent doc that ended up with the new init markers — including
    ones that were already at the new markers and were kept unchanged.
    """

    wrote_standards: bool
    wrote_init_block: bool
    init_block_targets: tuple[str, ...] = ()


# --- public operations ----------------------------------------------------


def install_for_agent_clis(agent_clis: list[AgentCli], *, home: Path | None = None) -> InstallManifest:
    """Map bundled resources to each agent CLI's native paths, write them
    idempotently (byte-identical reinstall), and record the manifest.

    Generic is always included in *agent_clis* — callers must prepend it.

    Each agent CLI's artifacts are described by ``_INSTALL_PLAN``: the persona
    file + skills tree, the rendered change agents, or both. An agent CLI absent
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
    """Re-write the rendered change agents for *agent_clis* without touching the install manifest.

    Use this for scoped refreshes — e.g. the ``set-models`` wizard editing
    ``overrides.json`` and re-emitting Claude's change agents — where calling
    ``install_for_agent_clis`` with a single CLI would clobber the entries
    for other installed CLIs in ``~/.ai-harness/installed.json``.

    Behaviour:

    - Only writers in ``_RENDER_PLAN`` run: the persona+skills writers are
      install-time artifacts that do not depend on override state and are
      intentionally left alone. Re-running them would re-copy the static
      template tree and add nothing.
    - CLIs without native change-agent support (GENERIC) are no-ops
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


def init_repo(
    repo_root: Path | None = None,
) -> InitResult:
    """Scaffold repo-local artifacts at *repo_root*.

    Writes a titles-only ``CODING_STANDARDS.md`` if it does not exist, and
    lands an identical init block on both ``CLAUDE.md`` and ``AGENTS.md``
    (creating either when absent). The block is wrapped in
    ``<!-- ai-harness:init:start -->`` / ``<!-- ai-harness:end -->`` and
    points at ``CODING_STANDARDS.md``. If either agent doc already carries
    the new init markers, it is left unchanged. If either carries the
    pre-refactor legacy ``<!-- ai-harness:start -->`` /
    ``<!-- ai-harness:end -->`` block, that block is replaced **in place**
    with the new init block (user content outside the markers survives
    byte-identical).

    Idempotent by per-artifact detection — no sentinel file. Returns an
    ``InitResult`` describing which artifacts were written.

    *repo_root* defaults to the current working directory so tests can drive
    the operation against a temporary directory.
    """
    root = repo_root if repo_root is not None else Path.cwd()

    wrote_standards = _write_coding_standards(root)
    wrote_init_block, init_block_targets = _write_init_block(root)

    return InitResult(
        wrote_standards=wrote_standards,
        wrote_init_block=wrote_init_block,
        init_block_targets=init_block_targets,
    )


# --- private helpers -------------------------------------------------------


def _resources_root() -> Path:
    """Resolve the bundled resources root as a concrete filesystem path."""
    return Path(str(files(_RESOURCE_PACKAGE))) / _RESOURCE_ROOT


def _walk_files(root: Path) -> list[Path]:
    """All regular files under *root*, sorted for deterministic output."""
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix())


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
    """Render the change agents for *cli* into *home*; return absolute paths written.

    Delegates override-store loading to ``render_agents`` (which reads
    ``~/.ai-harness/overrides.json`` itself), so a missing file is a no-op
    and a malformed file fails loudly — no pre-loading duplication here.
    """
    written: list[Path] = []
    for rendered in render_agents(cli, home=home):
        dest = home / rendered.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered.content, encoding="utf-8")
        written.append(dest)
    return written


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

_RENDER_PLAN: dict[AgentCli, list[_InstallWriter]] = {
    AgentCli.CLAUDE: [partial(_write_rendered_agents, cli=AgentCli.CLAUDE)],
    AgentCli.COPILOT: [partial(_write_rendered_agents, cli=AgentCli.COPILOT)],
    AgentCli.OPENCODE: [partial(_write_rendered_agents, cli=AgentCli.OPENCODE)],
}


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


def _write_coding_standards(root: Path) -> bool:
    """Write ``CODING_STANDARDS.md`` skeleton if absent; return whether written."""
    path = root / "CODING_STANDARDS.md"
    if path.exists():
        return False
    path.write_text(_CODING_STANDARDS_SKELETON, encoding="utf-8")
    return True


def _write_init_block(root: Path) -> tuple[bool, tuple[str, ...]]:
    """Drive the per-target init-block loop at *root*.

    For each candidate in ``_INIT_BLOCK_DOCS`` (deterministic order), dispatches
    to :func:`_apply_init_block` for the four-case decision (create / keep /
    migrate-legacy / bare-append). Every visited target is recorded in the
    returned tuple — including "kept" targets — so the CLI can echo per-target
    outcomes with a single loop.

    Returns ``(modified_any, targets)`` where *modified_any* is ``True`` when
    at least one target's bytes were changed by this call, and *targets* is the
    ordered tuple of agent docs that ended up carrying the new init markers.
    """
    targets: list[str] = []
    modified_any = False
    for name in _INIT_BLOCK_DOCS:
        path = root / name
        targets.append(name)
        if _apply_init_block(path):
            modified_any = True
    return modified_any, tuple(targets)


def _apply_init_block(path: Path) -> bool:
    """Apply the init-block action appropriate to *path*'s current state.

    The four-case table (mutually exclusive, checked in this order):

    1. **Missing** — ``not path.exists()``: create the file with ``_INIT_BLOCK``
       verbatim (no leading blank).
    2. **New markers present** — both ``_AI_HARNESS_INIT_START`` and
       ``_AI_HARNESS_INIT_END`` are substrings of the file: no-op.
    3. **Legacy markers present** — ``_AI_HARNESS_START`` or ``_AI_HARNESS_END``
       is a substring: replace the legacy block in place via
       :func:`_migrate_legacy_block` and write the result.
    4. **Bare file** — none of the above: ensure trailing newline, prepend a
       blank line, then append ``_INIT_BLOCK``.

    Returns ``True`` when the file's bytes were modified by this call
    (cases 1, 3, 4) and ``False`` when it was left untouched (case 2).
    """
    if not path.exists():
        # Case 1: missing — create with the managed block verbatim.
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_INIT_BLOCK, encoding="utf-8")
        return True

    content = path.read_text(encoding="utf-8")

    if content == "":
        # Empty file is treated as "no content yet" — write the managed block
        # verbatim so the start marker lands on the first line with no leading
        # blank. See spec scenario "empty CLAUDE.md receives the block".
        path.write_text(_INIT_BLOCK, encoding="utf-8")
        return True

    if _AI_HARNESS_INIT_START in content and _AI_HARNESS_INIT_END in content:
        # Case 2: new markers already present — keep unchanged.
        return False

    if _AI_HARNESS_START in content or _AI_HARNESS_END in content:
        # Case 3: legacy markers — surgical in-place migration.
        migrated = _migrate_legacy_block(content)
        path.write_text(migrated, encoding="utf-8")
        return True

    # Case 4: bare file — append with a separating blank line.
    if not content.endswith("\n"):
        content += "\n"
    content += "\n" + _INIT_BLOCK
    path.write_text(content, encoding="utf-8")
    return True


def _migrate_legacy_block(content: str) -> str:
    """Swap the legacy ``ai-harness:start``/``ai-harness:end`` block for ``_INIT_BLOCK``.

    The legacy block is the unique substring from the start-of-line containing
    ``<!-- ai-harness:start -->`` through the end-of-line containing
    ``<!-- ai-harness:end -->``, inclusive of both newline characters. It is
    replaced by ``_INIT_BLOCK`` (followed by a single ``\\n`` if the original
    ended with one; otherwise no trailing newline is added). Every byte before
    the start-of-line and every byte after the end-of-line newline is preserved
    unchanged — this is the user-content byte-preservation invariant.
    """
    lines = content.splitlines(keepends=True)
    start_idx = end_idx = None
    for i, line in enumerate(lines):
        if _AI_HARNESS_START in line:
            start_idx = i
        if _AI_HARNESS_END in line:
            end_idx = i
            break
    if start_idx is None or end_idx is None or end_idx < start_idx:
        # Defensive: caller has already classified this as legacy, so reaching
        # here indicates a degenerate file (start without end or vice versa).
        # Preserve the bytes verbatim — do not silently rewrite a half-state.
        return content
    return (
        "".join(lines[:start_idx])
        + _INIT_BLOCK
        + ("\n" if lines[end_idx].endswith("\n") else "")
        + "".join(lines[end_idx + 1 :])
    )
