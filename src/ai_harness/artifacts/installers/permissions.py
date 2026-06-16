"""Claude settings.json permission-rule management.

Deep-merges subagent tool allow-rules into ``~/.claude/settings.json``
``permissions.allow`` on install, removes them on uninstall, with
idempotency, marker tracking, and safe fallback heuristics.

Public surface (3 functions):
  install_permissions    — full install recipe (resolve, backup, compute, merge)
  uninstall_permissions  — full uninstall recipe (resolve, remove)
  compute_required_rules — pure function: parse frontmatter, map tools, dedup

Private helpers (4 functions, module-internal):
  _resolve_settings_path — CLAUDE_CONFIG_DIR or ~/.claude/settings.json
  _backup_settings       — copy-once backup with .ai-harness-backup suffix
  _merge_allow_rules     — deep-merge missing rules + write marker
  _remove_managed_rules  — marker-based removal with 5-name fallback
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

_logger = logging.getLogger(__name__)

# ── Tool-to-rule map (ADR-7) ─────────────────────────────────────────────────

TOOL_TO_RULE: dict[str, str] = {
    "Bash": "Bash",
    "Read": "Read",
    "Edit": "Edit",
    "Write": "Write",
    "Agent": "Agent",
    "Glob": "Read",
    "Grep": "Read",
}

# The five rule names the installer always manages (ADR-4 fallback).
_MANAGED_RULE_NAMES: set[str] = {"Bash", "Read", "Edit", "Write", "Agent"}

# ── Private helpers ───────────────────────────────────────────────────────────


def _parse_frontmatter_tools(path: Path) -> list[str]:
    """Extract the ``tools:`` list from a Markdown file's YAML frontmatter.

    Handles both YAML flow sequences ``[A, B]`` and scalar values ``A``.
    Returns an empty list when no ``tools:`` field is present.

    Raises :exc:`ValueError` when the frontmatter is malformed.
    """
    text = path.read_text(encoding="utf-8")

    # Frontmatter is the block between the first two ``---`` lines.
    if not text.startswith("---"):
        raise ValueError(f"No YAML frontmatter in {path}")

    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError(f"Unclosed YAML frontmatter in {path}")

    frontmatter = parts[1]

    match = re.search(r"^tools:\s*(.+)$", frontmatter, re.MULTILINE)
    if not match:
        return []  # no tools field — valid, just empty

    value = match.group(1).strip()

    # YAML flow sequence:  [Read, Edit, Write, Bash]
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip() for item in inner.split(",")]

    # Scalar value
    return [value]


# ── Public surface ────────────────────────────────────────────────────────────


def compute_required_rules(subagent_paths: list[Path]) -> set[str]:
    """Parse every sub-agent frontmatter, map tools to rules, return deduplicated union.

    Pure function — no I/O beyond reading the supplied paths.
    """
    rules: set[str] = set()
    for path in subagent_paths:
        tools = _parse_frontmatter_tools(path)
        for tool in tools:
            rule = TOOL_TO_RULE.get(tool, tool)
            rules.add(rule)
    return rules


# ── Stubs for remaining functions (filled in tasks 2.2–2.7) ───────────────────


def _resolve_settings_path() -> Path:
    """Return the path to ``settings.json``.

    Honors the ``CLAUDE_CONFIG_DIR`` environment variable; falls back to
    ``~/.claude/settings.json``.
    """
    import os

    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        return Path(config_dir) / "settings.json"
    return Path.home() / ".claude" / "settings.json"


def _backup_settings(settings_path: Path) -> None:
    """Create a byte-identical backup on first call; no-op if backup exists.

    Backup path: ``<settings_path>.ai-harness-backup``
    """
    backup_path = settings_path.with_suffix(
        settings_path.suffix + ".ai-harness-backup"
    )
    if backup_path.exists():
        return
    if not settings_path.is_file():
        return
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_bytes(settings_path.read_bytes())


def _merge_allow_rules(
    settings_path: Path, rules: set[str], marker_path: Path
) -> set[str]:
    """Deep-merge *rules* into ``permissions.allow``; write marker.

    Loads ``settings.json``, adds any missing *rules* to the
    ``permissions.allow`` array, and writes the result back (only when
    at least one rule was added).  The *marker_path* is written with
    the full managed-rule set.  Returns the set of rules that were
    actually added (empty when all rules were already present —
    idempotent).
    """
    if settings_path.is_file():
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    else:
        data = {}

    permissions = data.setdefault("permissions", {})
    existing: list[str] = permissions.get("allow", [])
    existing_set = set(existing)

    added = rules - existing_set
    if not added:
        return set()

    new_allow = existing + sorted(added)
    permissions["allow"] = new_allow
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(
        json.dumps(sorted(rules), indent=2) + "\n", encoding="utf-8"
    )
    return added


def install_permissions(subagent_paths: list[Path]) -> set[str]:
    """Full install sequence (5-step recipe).

    1. Resolve ``settings.json`` path (honouring ``CLAUDE_CONFIG_DIR``).
    2. Back it up (no-op if backup already exists).
    3. Compute the required permission rules from sub-agent frontmatters.
    4. Deep-merge missing rules into ``permissions.allow``.
    5. Write the marker file.

    Returns the set of rules actually added (empty on idempotent reinstall).
    """
    settings_path = _resolve_settings_path()
    _backup_settings(settings_path)
    rules = compute_required_rules(subagent_paths)
    if not rules:
        return set()
    marker_path = settings_path.parent / ".ai-harness-managed-allow.json"
    return _merge_allow_rules(settings_path, rules, marker_path)


def _remove_managed_rules(
    settings_path: Path, marker_path: Path
) -> set[str]:
    """Remove marker-tracked rules from ``permissions.allow``; delete marker.

    Reads the marker file to learn which rules were managed.  Removes
    only those rules from the ``permissions.allow`` array, leaving any
    user-added rules intact.  Deletes the marker on success.

    **Fallback**: when the marker is missing or contains invalid JSON,
    removes the five known managed rule names (``Bash``, ``Read``,
    ``Edit``, ``Write``, ``Agent``) instead.  A warning is logged in
    that case.
    """
    # Determine which rules to remove.
    managed: set[str]
    fallback = False

    if marker_path.is_file():
        try:
            raw = marker_path.read_text(encoding="utf-8").strip()
            if not raw:
                fallback = True
            else:
                managed = set(json.loads(raw))
        except (json.JSONDecodeError, ValueError, TypeError):
            fallback = True
    else:
        fallback = True

    if fallback:
        _logger.warning(
            "Marker %s missing or corrupt — falling back to 5-name heuristic",
            marker_path,
        )
        managed = _MANAGED_RULE_NAMES.copy()

    if not settings_path.is_file():
        return set()

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    allow: list[str] = data.get("permissions", {}).get("allow", [])
    if not allow:
        return set()

    new_allow = [r for r in allow if r not in managed]
    removed = {r for r in allow if r in managed}

    if not removed:
        return set()

    data["permissions"]["allow"] = new_allow
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    # Clean up marker — always delete on uninstall, including the
    # corrupt-marker fallback case (we no longer need the invalid file).
    if marker_path.is_file():
        marker_path.unlink()

    return removed


def uninstall_permissions() -> set[str]:
    """Full uninstall sequence.

    1. Resolve ``settings.json`` path.
    2. Remove marker-tracked rules from ``permissions.allow``.
    3. Delete the marker (handled by :func:`_remove_managed_rules`).

    Returns the set of rules actually removed.
    """
    settings_path = _resolve_settings_path()
    marker_path = settings_path.parent / ".ai-harness-managed-allow.json"
    return _remove_managed_rules(settings_path, marker_path)
