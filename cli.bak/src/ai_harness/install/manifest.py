"""Manifest: central registry of owned installed files.

The manifest survives reinstalls and is the single source of truth for
uninstall: only files listed here are removed. The on-disk schema is
identical to the Go implementation (``version`` + ``installed`` list of
``{dest, source?, kind}``) so existing user installs can be uninstalled by
the Python port without re-running the installer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "install-manifest.json"
MANIFEST_DIRNAME = "ai-harness"


@dataclass(frozen=True)
class ManifestEntry:
    """One owned installed file.

    ``source`` is informational; ``dest`` is what uninstall removes.
    ``kind`` must be ``"file"`` (the only kind supported today); the field
    is kept so future kinds (e.g. ``"directory"``) are forward-compatible.
    """

    dest: str
    source: str = ""
    kind: str = "file"


@dataclass
class Manifest:
    version: int = MANIFEST_VERSION
    installed: list[ManifestEntry] = field(default_factory=list)


def manifest_path(opencode_dir: Path) -> Path:
    """Return the absolute path of the manifest file for a given OpenCode dir.

    The manifest lives in ``<opencode_dir parent>/ai-harness/`` — the same
    location the Go installer uses, so Python and Go stay interchangeable.
    """
    return opencode_dir.parent / MANIFEST_DIRNAME / MANIFEST_FILENAME


def _read_json(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _validated_entry(entry: object) -> ManifestEntry | None:
    """Construct a ManifestEntry from a raw dict, or return ``None`` when
    the entry is missing required fields or has non-string values.

    The function validates field types so that a schema-invalid entry
    (e.g. ``"dest": 123``) is silently skipped rather than loaded and
    then crashing later in ``validate_manifest_entry`` with a TypeError.
    """
    if not isinstance(entry, dict):
        return None
    dest = entry.get("dest")
    if not isinstance(dest, str):
        return None
    source = entry.get("source", "")
    if not isinstance(source, str):
        return None
    kind = entry.get("kind", "file")
    if not isinstance(kind, str):
        return None
    return ManifestEntry(dest=dest, source=source, kind=kind)


def read_manifest(opencode_dir: Path) -> Manifest | None:
    """Load the manifest, or return ``None`` when no manifest exists.

    A missing manifest is the expected uninstall precondition (nothing to
    remove). A malformed manifest is also treated as missing rather than
    fatal so a corrupted file does not brick the user's home dir.

    Individual entries that are schema-invalid (non-string ``dest``,
    non-dict entries, etc.) are silently skipped; valid entries in the
    same manifest still load.
    """
    payload = _read_json(manifest_path(opencode_dir))
    if payload is None:
        return None
    try:
        installed: list[ManifestEntry] = []
        for entry in payload.get("installed", []):
            validated = _validated_entry(entry)
            if validated is not None:
                installed.append(validated)
    except (TypeError, AttributeError):
        # ``payload`` may be a list or other non-dict JSON that lacks ``.get``.
        return None
    try:
        version = int(payload.get("version", MANIFEST_VERSION))
    except (ValueError, TypeError):
        # version field may be a non-integer string (e.g. "latest").
        return None
    return Manifest(version=version, installed=installed)


def owned_roots(opencode_dir: Path) -> list[Path]:
    """Return the directories the manifest validator considers managed.

    Sibling of ``opencode_dir`` (so the manifest itself is in a managed
    root) plus the well-known harness config directories. The Go side
    resolves the latter from the same $HOME-anchored layout.
    """
    config_dir = opencode_dir.parent
    home = config_dir.parent
    return [
        home / ".claude",
        home / ".agents",
        home / ".copilot",
        opencode_dir,
        config_dir / MANIFEST_DIRNAME,
    ]


def _clean(dest: str) -> Path:
    return Path(os.path.normpath(dest))


def _is_within(candidate: Path, root: Path) -> bool:
    """Return whether ``candidate`` is strictly inside ``root``."""
    try:
        relative = candidate.relative_to(root)
    except ValueError:
        return False
    return relative.parts != (".")


def validate_manifest_entry(opencode_dir: Path, entry: ManifestEntry) -> Path:
    """Return the safe absolute dest path or raise :class:`ValueError`.

    The validator enforces the same rules the Go installer uses: the
    manifest entry must describe a regular file under a managed root.
    Anything else is rejected before any destructive operation runs.

    Parent-directory symlinks are resolved so a symlink inside a managed
    root that points outside cannot smuggle an outside file through the
    string-based containment check.  Final-path symlinks are still
    rejected; the leaf must be a regular file (or absent, which is fine
    for uninstall).
    """
    if entry.kind != "file":
        raise ValueError(
            f"unsafe manifest entry {entry.dest}: unsupported kind {entry.kind!r}"
        )
    if not os.path.isabs(entry.dest):
        raise ValueError(
            f"unsafe manifest entry {entry.dest}: destination must be absolute"
        )
    cleaned = _clean(entry.dest)
    roots = owned_roots(opencode_dir)
    for root in roots:
        if not _is_within(cleaned, root):
            continue
        # Resolve parent-directory symlinks and verify the real filesystem
        # location is still within real managed roots. ``resolve()``
        # follows symlinks for any existing components (including parent
        # directories) but does not require the final leaf to exist.
        real_path = cleaned.resolve()
        real_roots = [r.resolve() for r in roots]
        if not any(_is_within(real_path, rr) for rr in real_roots):
            raise ValueError(
                f"unsafe manifest entry {entry.dest}: "
                "parent directory symlink resolves outside managed roots"
            )
        if not cleaned.exists():
            return cleaned
        if not cleaned.is_file() or cleaned.is_symlink():
            raise ValueError(
                f"unsafe manifest entry {entry.dest}: "
                "kind file target is not a regular file"
            )
        return cleaned
    raise ValueError(
        f"unsafe manifest entry {entry.dest}: "
        "destination is outside ai-harness managed roots"
    )


def _dedupe(entries: list[ManifestEntry]) -> list[ManifestEntry]:
    """Keep the last entry per ``dest`` and sort by (dest, source).

    Mirrors the Go ``dedupeAndSort`` so a Python and a Go write of the
    same logical manifest produce the same on-disk order — useful for
    diff-friendly parity tests and human inspection.
    """
    by_dest: dict[str, ManifestEntry] = {}
    for entry in entries:
        by_dest[entry.dest] = entry
    return sorted(by_dest.values(), key=lambda e: (e.dest, e.source))


def write_manifest(opencode_dir: Path, entries: list[ManifestEntry]) -> None:
    """Persist ``entries`` merged with the existing manifest on disk.

    Narrow re-installs touch only a subset of the artifacts; the merge
    preserves older ownership so a later uninstall still knows what the
    installer owns. A re-install of an already-owned path replaces (not
    duplicates) its manifest entry.
    """
    path = manifest_path(opencode_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_manifest(opencode_dir)
    merged: list[ManifestEntry] = list(existing.installed) if existing else []
    merged.extend(entries)
    manifest = Manifest(version=MANIFEST_VERSION, installed=_dedupe(merged))
    payload = {
        "version": manifest.version,
        "installed": [
            {"dest": entry.dest, "source": entry.source, "kind": entry.kind}
            for entry in manifest.installed
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
