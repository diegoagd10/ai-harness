"""Artifact discovery and completeness classification."""

from __future__ import annotations

import os

from .models import (
    ARTIFACT_DONE,
    ARTIFACT_MISSING,
    ARTIFACT_PARTIAL,
    ArtifactPaths,
)

SPEC_FILE_NAME = "spec.md"


def discover_artifact_paths(change_root: str) -> ArtifactPaths:
    """Find the on-disk paths for every artifact kind under a change root.
    Single-file artifacts yield a one-element list when present; specs are
    discovered by a recursive walk for files named exactly spec.md."""
    paths = ArtifactPaths()
    paths.proposal = _existing_file(os.path.join(change_root, "proposal.md"))
    paths.design = _existing_file(os.path.join(change_root, "design.md"))
    paths.tasks = _existing_file(os.path.join(change_root, "tasks.md"))
    paths.apply_progress = _existing_file(os.path.join(change_root, "apply-progress.md"))
    paths.verify_report = _existing_file(os.path.join(change_root, "verify-report.md"))
    paths.specs = _find_spec_files(os.path.join(change_root, "specs"))
    return paths


def classify_artifacts(change_root: str, paths: ArtifactPaths) -> dict[str, str]:
    """Map each discovered artifact to its completeness state."""
    return {
        "proposal": _file_artifact_state(paths.proposal),
        "specs": _specs_artifact_state(paths.specs, os.path.join(change_root, "specs")),
        "design": _file_artifact_state(paths.design),
        "tasks": _file_artifact_state(paths.tasks),
        "applyProgress": _file_artifact_state(paths.apply_progress),
        "verifyReport": _file_artifact_state(paths.verify_report),
    }


def _existing_file(path: str) -> list[str]:
    return [path] if os.path.exists(path) else []


def _find_spec_files(specs_root: str) -> list[str]:
    """Recursively collect every file named exactly spec.md under specs_root,
    sorted. A missing or non-directory specs root yields an empty list; any other
    read error (e.g. permission denied) propagates, matching Go's WalkDir."""
    files: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(specs_root, onerror=_reraise_walk_error):
        for name in filenames:
            if name == SPEC_FILE_NAME:
                files.append(os.path.join(dirpath, name))
    files.sort()
    return files


def _reraise_walk_error(error: OSError) -> None:
    """os.walk error callback. Go's filepath.WalkDir treats a missing or
    non-directory specs root as "no specs" (empty list) but propagates other read
    errors so the CLI exits 1. Mirror that: swallow not-found/not-a-dir, re-raise
    the rest (notably PermissionError)."""
    if isinstance(error, (FileNotFoundError, NotADirectoryError)):
        return
    raise error


def _file_artifact_state(paths: list[str]) -> str:
    """Classify a single-file artifact: missing when absent, partial when present
    but blank, done when it has non-whitespace content."""
    if not paths:
        return ARTIFACT_MISSING
    return ARTIFACT_DONE if _has_content(paths[0]) else ARTIFACT_PARTIAL


def _specs_artifact_state(paths: list[str], specs_root: str) -> str:
    """Classify the specs artifact: missing when no specs dir, partial when the
    dir is non-empty but lacks usable spec.md files, done when every discovered
    spec.md has content."""
    if not paths:
        try:
            with os.scandir(specs_root) as entries:
                if any(True for _ in entries):
                    return ARTIFACT_PARTIAL
        except (FileNotFoundError, NotADirectoryError):
            return ARTIFACT_MISSING
        return ARTIFACT_MISSING
    for path in paths:
        if not _has_content(path):
            return ARTIFACT_PARTIAL
    return ARTIFACT_DONE


def _has_content(path: str) -> bool:
    """Report whether the file exists and contains non-whitespace text."""
    try:
        # errors="replace" mirrors Go's lossy string(bytes): invalid UTF-8 never
        # raises, so a non-UTF-8 artifact is still classified by its content.
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read().strip() != ""
    except OSError:
        return False
