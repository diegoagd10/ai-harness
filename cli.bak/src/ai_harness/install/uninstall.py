"""uninstall: remove every manifest-owned file, then the manifest itself.

The narrow-selection case honours ``cfg.harnesses`` (Go ignores ``--harness``
on uninstall); the Python port uses the manifest as the source of truth and
filters the entries down to the selected harnesses. An unsafe manifest is
rejected before any file is removed.

All entries — including generated OpenCode artifacts such as slash-command
files and ``opencode.json`` — are removed through the same manifest-driven
loop, so no repo access is required for uninstall.
"""

from __future__ import annotations

from pathlib import Path

from .config import Config
from .harness import Harness
from .manifest import ManifestEntry, manifest_path, read_manifest
from .ops import Outcome, uninstall_entry


def _entries_for_harnesses(
    cfg: Config, entries: list[ManifestEntry], harnesses: list[Harness]
) -> list[ManifestEntry]:
    """Filter manifest entries to the selected harness roots.

    Entries outside any of the selected roots are dropped: they cannot
    belong to a harness the user picked, and uninstalling them would
    silently remove other things. The .agents artifacts are owned by
    every selected harness by convention, so they survive. Generated
    OpenCode artifacts (slash-command files and ``opencode.json``) are
    owned by the opencode harness and only touched when the user picked
    opencode explicitly.
    """
    if not harnesses:
        return entries
    selected_roots: set[Path] = set()
    if Harness.CLAUDE in harnesses:
        selected_roots.add(cfg.claude_dir)
    if Harness.COPILOT in harnesses:
        selected_roots.add(cfg.copilot_dir)
    if Harness.OPENCODE in harnesses:
        selected_roots.add(cfg.opencode_dir)
    # Only include .agents when the selected harnesses cover every
    # harness that currently owns entries in the manifest.  If a
    # harness NOT in the selection still has entries, removing the
    # shared .agents artifacts would leave that harness broken.
    harnesses_with_entries: set[Harness] = set()
    for entry in entries:
        dest = Path(entry.dest)
        if _is_within(dest, cfg.claude_dir):
            harnesses_with_entries.add(Harness.CLAUDE)
        if _is_within(dest, cfg.copilot_dir):
            harnesses_with_entries.add(Harness.COPILOT)
        if _is_within(dest, cfg.opencode_dir):
            harnesses_with_entries.add(Harness.OPENCODE)
    if harnesses_with_entries.issubset(set(harnesses)):
        selected_roots.add(cfg.agents_dir)
    opencode_commands_dir = cfg.opencode_dir / "commands"
    opencode_json = cfg.opencode_dir / "opencode.json"
    opencode_selected = Harness.OPENCODE in harnesses
    filtered: list[ManifestEntry] = []
    for entry in entries:
        dest = Path(entry.dest)
        if not opencode_selected and (
            _is_within(dest, opencode_commands_dir) or dest == opencode_json
        ):
            # These belong to opencode; only remove them when opencode was picked.
            continue
        if any(_is_within(dest, root) for root in selected_roots):
            filtered.append(entry)
    return filtered


def _is_within(path: Path, root: Path) -> bool:
    """Return whether ``path`` is strictly inside ``root`` (or equals it)."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def detect_installed_harnesses(cfg: Config) -> list[Harness]:
    """Return the harnesses that currently own at least one manifest entry.

    Used by the uninstall picker so the menu can pre-select the harnesses
    the user previously installed. OpenCode also counts as installed when
    the generated ``opencode.json`` or any slash-command file is on disk,
    even if the manifest predates the generator step.
    """
    manifest = read_manifest(cfg.opencode_dir)
    installed: set[Harness] = set()
    if manifest is not None:
        for entry in manifest.installed:
            dest = Path(entry.dest)
            if _is_within(dest, cfg.claude_dir):
                installed.add(Harness.CLAUDE)
            if _is_within(dest, cfg.copilot_dir):
                installed.add(Harness.COPILOT)
            if _is_within(dest, cfg.opencode_dir):
                installed.add(Harness.OPENCODE)
    if (cfg.opencode_dir / "opencode.json").exists():
        installed.add(Harness.OPENCODE)
    if (cfg.opencode_dir / "commands").is_dir() and any(
        (cfg.opencode_dir / "commands").iterdir()
    ):
        installed.add(Harness.OPENCODE)
    return [harness for harness in Harness if harness in installed]


def uninstall(cfg: Config) -> tuple[list[Outcome], str | None]:
    """Remove manifest-owned files in ``cfg``; return (report, error).

    The function validates every entry BEFORE any destructive operation
    so an unsafe manifest fails closed. The manifest file itself is
    removed only when no entries remain; a narrow uninstall that leaves
    other harnesses' files alone keeps the manifest so the next run can
    still see what the installer owns.

    All entries — including generated OpenCode artifacts (slash-command
    files and ``opencode.json``) — are removed through the same
    manifest-driven loop, so no repo is required for uninstall.
    """
    from .manifest import validate_manifest_entry, write_manifest

    manifest = read_manifest(cfg.opencode_dir)
    if manifest is None:
        return [], None
    # Validate the ENTIRE manifest BEFORE narrowing to the selected
    # harnesses.  An unsafe entry outside the selection must still
    # cause atomic rejection so a tampered manifest cannot slip
    # through a narrow uninstall.  This is the atomicity guarantee
    # the Go test ``TestUninstallRejectsUnsafeManifestAtomically``
    # exercises; the Python port extends it to narrow selections via
    # ``test_uninstall_narrow_rejects_unsafe_entry_outside_selection``.
    for entry in manifest.installed:
        try:
            validate_manifest_entry(cfg.opencode_dir, entry)
        except ValueError as err:
            return [], str(err)
    entries = _entries_for_harnesses(cfg, manifest.installed, cfg.harnesses)
    report: list[Outcome] = []
    for entry in entries:
        outcome = uninstall_entry(cfg.opencode_dir, entry)
        report.append(outcome)
    # The manifest merge contract is "additive": write_manifest keeps
    # whatever is already on disk and appends the new entries. We want
    # the opposite here — replace the manifest with only the survivors
    # (those NOT in the uninstalled selection). Removing the file first
    # forces write_manifest to start from a clean slate, then we write
    # just the survivors.
    removed_dests = {entry.dest for entry in entries}
    surviving = [entry for entry in manifest.installed if entry.dest not in removed_dests]
    try:
        manifest_path(cfg.opencode_dir).unlink()
    except FileNotFoundError:
        pass
    if surviving:
        write_manifest(cfg.opencode_dir, surviving)
    return report, None
