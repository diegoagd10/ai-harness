"""Manifest: central registry of owned installed files.

The manifest survives reinstalls and is the single source of truth for
uninstall: only files listed here are removed. The on-disk schema is
identical to the Go implementation (``version`` + ``installed`` list of
``{dest, source?, kind}``) so existing user installs can be uninstalled
by the Python port without re-running the installer.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_harness.install.manifest import (
    MANIFEST_VERSION,
    ManifestEntry,
    manifest_path,
    read_manifest,
    write_manifest,
)

# --- manifest_path ---------------------------------------------------------


def test_manifest_path_lives_in_ai_harness_sibling(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    expected = tmp_path / ".config" / "ai-harness" / "install-manifest.json"
    assert manifest_path(opencode_dir) == expected


# --- Manifest round-trip ---------------------------------------------------


def test_manifest_round_trip_preserves_entries(tmp_path: Path) -> None:
    entries = [
        ManifestEntry(dest=str(tmp_path / "a.md"), source="/repo/a.md", kind="file"),
        ManifestEntry(dest=str(tmp_path / "b.md"), source="/repo/b.md", kind="file"),
    ]
    opencode_dir = tmp_path / ".config" / "opencode"
    write_manifest(opencode_dir, entries)
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    assert loaded.version == MANIFEST_VERSION
    # Order-insensitive comparison: dedupeAndSort in the Go side guarantees
    # stable ordering by (dest, source) but the on-disk contract is the
    # entries' values, not their sequence.
    loaded_dests = sorted(entry.dest for entry in loaded.installed)
    assert loaded_dests == sorted(entry.dest for entry in entries)


def test_manifest_read_missing_returns_none(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    assert read_manifest(opencode_dir) is None


def test_manifest_read_malformed_json_treated_as_missing(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    manifest_path(opencode_dir).write_text("{ not valid json [[[", encoding="utf-8")
    assert read_manifest(opencode_dir) is None


def test_manifest_read_empty_file_treated_as_missing(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    manifest_path(opencode_dir).write_text("", encoding="utf-8")
    assert read_manifest(opencode_dir) is None


def test_manifest_writes_to_disk(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    write_manifest(opencode_dir, [ManifestEntry(dest="/x", kind="file")])
    on_disk = json.loads(manifest_path(opencode_dir).read_text(encoding="utf-8"))
    assert on_disk["version"] == MANIFEST_VERSION
    assert on_disk["installed"] == [{"dest": "/x", "source": "", "kind": "file"}]


def test_manifest_write_creates_parent_dir(tmp_path: Path) -> None:
    opencode_dir = tmp_path / "deeply" / "nested" / "opencode"
    write_manifest(opencode_dir, [ManifestEntry(dest="/x", kind="file")])
    assert manifest_path(opencode_dir).exists()


# --- Manifest merging ------------------------------------------------------


def test_manifest_write_merges_with_existing(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    write_manifest(
        opencode_dir,
        [ManifestEntry(dest="/a", kind="file"), ManifestEntry(dest="/b", kind="file")],
    )
    # Narrow re-install: only /b is touched this run; the existing /a entry
    # must remain so a later uninstall still knows it owns /a.
    write_manifest(opencode_dir, [ManifestEntry(dest="/b", kind="file")])
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    dests = sorted(entry.dest for entry in loaded.installed)
    assert dests == ["/a", "/b"]


def test_manifest_write_dedupes_overlapping_entries(tmp_path: Path) -> None:
    opencode_dir = tmp_path / ".config" / "opencode"
    write_manifest(
        opencode_dir,
        [ManifestEntry(dest="/a", source="/old", kind="file")],
    )
    # Re-install /a from a new source; the second write replaces, not appends.
    write_manifest(
        opencode_dir,
        [ManifestEntry(dest="/a", source="/new", kind="file")],
    )
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    assert len(loaded.installed) == 1
    assert loaded.installed[0].source == "/new"


# --- Manifest validation --------------------------------------------------


def test_manifest_entry_rejects_non_file_kind(tmp_path: Path) -> None:
    from ai_harness.install.manifest import validate_manifest_entry

    opencode_dir = tmp_path / ".config" / "opencode"
    with pytest.raises(ValueError, match="kind"):
        validate_manifest_entry(
            opencode_dir,
            ManifestEntry(dest=str(tmp_path / "x"), kind="directory"),
        )


def test_manifest_entry_rejects_relative_path(tmp_path: Path) -> None:
    from ai_harness.install.manifest import validate_manifest_entry

    opencode_dir = tmp_path / ".config" / "opencode"
    with pytest.raises(ValueError, match="absolute"):
        validate_manifest_entry(
            opencode_dir,
            ManifestEntry(dest="relative/path.md", kind="file"),
        )


def test_manifest_entry_rejects_path_outside_managed_roots(tmp_path: Path) -> None:
    from ai_harness.install.manifest import validate_manifest_entry

    opencode_dir = tmp_path / ".config" / "opencode"
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        validate_manifest_entry(
            opencode_dir,
            ManifestEntry(dest=str(outside), kind="file"),
        )


def test_manifest_entry_accepts_missing_file_in_managed_root(tmp_path: Path) -> None:
    # The validator must not fail when the file is absent; uninstall just
    # records the entry as absent and moves on.
    from ai_harness.install.manifest import validate_manifest_entry

    opencode_dir = tmp_path / ".config" / "opencode"
    safe = opencode_dir / "AGENTS.md"
    cleaned = validate_manifest_entry(
        opencode_dir,
        ManifestEntry(dest=str(safe), kind="file"),
    )
    assert cleaned == safe


def test_manifest_entry_rejects_directory_pointed_at_as_file(tmp_path: Path) -> None:
    from ai_harness.install.manifest import validate_manifest_entry

    opencode_dir = tmp_path / ".config" / "opencode"
    target = opencode_dir / "skills"
    target.mkdir(parents=True)
    (target / "leaf.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="not a regular file"):
        validate_manifest_entry(
            opencode_dir,
            ManifestEntry(dest=str(target), kind="file"),
        )
    # The directory's contents must remain untouched.
    assert (target / "leaf.txt").read_text(encoding="utf-8") == "keep"


def test_manifest_entry_rejects_parent_symlink_pointing_outside(
    tmp_path: Path,
) -> None:
    """Validator must reject a path whose parent directory is a symlink
    that resolves outside managed roots.

    The string-based ``_is_within`` check passes, but the real filesystem
    operation would follow the symlink and delete a file outside any
    managed root.
    """
    from ai_harness.install.manifest import validate_manifest_entry

    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)

    # Place a file outside all managed roots.
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_file = outside_dir / "danger.txt"
    outside_file.write_text("must survive", encoding="utf-8")

    # Create a symlink inside the managed root pointing outside.
    link_inside = opencode_dir / "escape"
    link_inside.symlink_to(outside_dir, target_is_directory=True)

    # The manifest entry dest is the symlinked path + file.
    target_via_link = link_inside / "danger.txt"
    entry = ManifestEntry(dest=str(target_via_link), kind="file")

    with pytest.raises(ValueError, match="parent"):
        validate_manifest_entry(opencode_dir, entry)

    # The outside file must remain untouched.
    assert outside_file.read_text(encoding="utf-8") == "must survive"


def test_manifest_entry_rejects_parent_symlink_escape_missing_file(
    tmp_path: Path,
) -> None:
    """Even when the target file does NOT exist, a parent-directory symlink
    pointing outside must be rejected — otherwise a later file creation
    could be redirected outside managed roots.

    Validator must NOT require the target to exist to detect this.
    """
    from ai_harness.install.manifest import validate_manifest_entry

    opencode_dir = tmp_path / ".config" / "opencode"
    opencode_dir.mkdir(parents=True)

    outside_dir = tmp_path / "outside2"
    outside_dir.mkdir()

    link_inside = opencode_dir / "escape2"
    link_inside.symlink_to(outside_dir, target_is_directory=True)

    # File does NOT exist yet, but parent symlink resolves outside.
    target_via_link = link_inside / "nonexistent.md"
    entry = ManifestEntry(dest=str(target_via_link), kind="file")

    with pytest.raises(ValueError, match="parent"):
        validate_manifest_entry(opencode_dir, entry)


# --- read_manifest schema-invalid payloads --------------------------------


def test_manifest_read_non_dict_json_treated_as_missing(tmp_path: Path) -> None:
    """A valid JSON array (not a dict) must be treated as missing
    rather than raising an AttributeError on ``.get``."""
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    manifest_path(opencode_dir).write_text('[{"dest":"/x","kind":"file"}]', encoding="utf-8")
    assert read_manifest(opencode_dir) is None


def test_manifest_read_invalid_version_field_treated_as_missing(
    tmp_path: Path,
) -> None:
    """A manifest with a non-integer version field must be treated as
    missing rather than raising ValueError from ``int()``."""
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    manifest_path(opencode_dir).write_text(
        '{"version":"not-a-number","installed":[]}', encoding="utf-8"
    )
    assert read_manifest(opencode_dir) is None


# --- read_manifest schema-invalid entries ----------------------------------


def test_manifest_read_skips_non_string_dest(
    tmp_path: Path,
) -> None:
    """An entry whose ``dest`` is not a string must be skipped rather
    than loaded as a ManifestEntry that would later fail with TypeError."""
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    payload = {
        "version": 1,
        "installed": [
            {"dest": 123, "source": "/repo/a.md", "kind": "file"},
            {"dest": str(tmp_path / "valid.md"), "source": "/repo/b.md", "kind": "file"},
        ],
    }
    manifest_path(opencode_dir).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    assert len(loaded.installed) == 1
    assert loaded.installed[0].dest == str(tmp_path / "valid.md")


def test_manifest_read_skips_non_dict_entry(
    tmp_path: Path,
) -> None:
    """A non-dict entry (e.g. a string) in the installed list must be
    skipped rather than raising AttributeError."""
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    payload = {
        "version": 1,
        "installed": [
            "not-a-dict",
            {"dest": str(tmp_path / "valid.md"), "source": "/repo/a.md", "kind": "file"},
        ],
    }
    manifest_path(opencode_dir).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    assert len(loaded.installed) == 1
    assert loaded.installed[0].dest == str(tmp_path / "valid.md")


def test_manifest_read_skips_non_string_source(
    tmp_path: Path,
) -> None:
    """An entry whose ``source`` is not a string must be skipped.
    Though ``source`` is informational, a non-string value signals
    a corrupted manifest that should not be trusted."""
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    payload = {
        "version": 1,
        "installed": [
            {"dest": str(tmp_path / "bad.md"), "source": 456, "kind": "file"},
            {"dest": str(tmp_path / "good.md"), "source": "/repo/a.md", "kind": "file"},
        ],
    }
    manifest_path(opencode_dir).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    assert len(loaded.installed) == 1
    assert loaded.installed[0].dest == str(tmp_path / "good.md")


def test_manifest_read_skips_non_string_kind(
    tmp_path: Path,
) -> None:
    """An entry whose ``kind`` is not a string must be skipped."""
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    payload = {
        "version": 1,
        "installed": [
            {"dest": str(tmp_path / "bad.md"), "kind": 42},
            {"dest": str(tmp_path / "good.md"), "kind": "file"},
        ],
    }
    manifest_path(opencode_dir).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    assert len(loaded.installed) == 1
    assert loaded.installed[0].dest == str(tmp_path / "good.md")


def test_manifest_read_all_valid_entries_survive(
    tmp_path: Path,
) -> None:
    """When all entries are valid, none should be skipped."""
    opencode_dir = tmp_path / ".config" / "opencode"
    manifest_path(opencode_dir).parent.mkdir(parents=True)
    payload = {
        "version": 1,
        "installed": [
            {"dest": str(tmp_path / "a.md"), "source": "/repo/a.md", "kind": "file"},
            {"dest": str(tmp_path / "b.md"), "kind": "file"},
            {"dest": str(tmp_path / "c.md"), "source": "/repo/c.md"},
        ],
    }
    manifest_path(opencode_dir).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    loaded = read_manifest(opencode_dir)
    assert loaded is not None
    assert len(loaded.installed) == 3
