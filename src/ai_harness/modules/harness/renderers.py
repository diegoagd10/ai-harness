"""DEPRECATED shim — backward-compat surface for the renderer module.

This module is the deprecated home of ``render_agents``, ``get_agent_meta``,
``write_override_store``, and ``RenderedFile``. The load-bearing public
seam now lives in
:mod:`ai_harness.modules.harness.administrators`; new code MUST select an
administrator from ``ADMINISTRATORS`` and call
:meth:`render_artifacts` polymorphically.

This module is kept for the migration window so internal legacy callers
and external users can continue to import the deprecated symbols. The
legacy code path (``_render_*`` returning ``RenderedFile``) is fully
self-contained below — it does NOT depend on the new administrator
subpackage — so a future cleanup that removes the deprecation entirely
won't cascade into the new package.

Re-exports from administrators (back-compat)
--------------------------------------------
The following are re-imported from the new administrator package so
existing ``from ai_harness.modules.harness.renderers import X`` imports
keep working:

- Public types: ``Artifact``, ``AgentMetadata``, ``AgentCaps``,
  ``ArtifactsAdministrator``
- Concrete administrators and dispatch:
  ``ClaudeArtifactsAdministrator``, ``OpenCodeArtifactsAdministrator``,
  ``CopilotArtifactsAdministrator``, ``ADMINISTRATORS``
- Public loaders/discovery: ``load_agent_metadata``,
  ``discover_agent_names``
- Per-provider helpers used by the legacy ``_render_*`` paths:
  ``_claude_tools`` (re-exported from
  :mod:`ai_harness.modules.harness.administrators.claude`),
  ``_opencode_permission`` (re-exported from
  :mod:`ai_harness.modules.harness.administrators.opencode`)
- Shared rendering helpers used by the legacy ``_render_*`` paths:
  ``_yaml_dump_frontmatter``, ``_read_template_body`` (re-exported from
  :mod:`ai_harness.modules.harness.administrators.base`)
"""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from pathlib import Path
from typing import NamedTuple

from ai_harness.modules.harness.administrators import (
    ADMINISTRATORS,
    AgentCaps,
    AgentMetadata,
    Artifact,
    ArtifactsAdministrator,
    ClaudeArtifactsAdministrator,
    CopilotArtifactsAdministrator,
    OpenCodeArtifactsAdministrator,
)
from ai_harness.modules.harness.administrators import base as _admin_base
from ai_harness.modules.harness.administrators.base import (  # noqa: F401  re-exported for tests/mock paths
    _agent_metadata_root,
    _decode_agent_caps,
    _decode_agent_metadata,
    _decode_effort_map,
    _decode_model_map,
    _decode_permission,
    _load_agent_metadata,
    _read_template_body,
    _validate_metadata_schema,
    _yaml_dump_frontmatter,
)
from ai_harness.modules.harness.administrators.claude import _claude_tools
from ai_harness.modules.harness.administrators.opencode import _opencode_permission
from ai_harness.modules.harness.models import AgentCli

__all__ = [
    "ADMINISTRATORS",
    "AgentCaps",
    "AgentMetadata",
    "Artifact",
    "ArtifactsAdministrator",
    "ClaudeArtifactsAdministrator",
    "CopilotArtifactsAdministrator",
    "OpenCodeArtifactsAdministrator",
    "discover_agent_names",
    "load_agent_metadata",
]


# ---------------------------------------------------------------------------
# Legacy deprecated types and constants
# ---------------------------------------------------------------------------


class RenderedFile(NamedTuple):
    """One rendered agent file: a home-relative path and the file's full content.

    Every renderer in this module's legacy code path returns a
    :class:`RenderedFile` so callers can read ``.filename`` and ``.content``
    without remembering positional order. The single legacy entry
    :func:`render_agents` yields a list of these — kept for the migration
    window only.
    """

    filename: str
    content: str


# Local copy of ``_AGENT_RESOURCE_DIRS`` — kept independent of the
# canonical :data:`administrators.base._AGENT_RESOURCE_DIRS` so test
# mocks targeting ``renderers._AGENT_RESOURCE_DIRS`` continue to affect
# this module's legacy discovery without re-importing the canonical
# tuple (which the new admin package owns).
_AGENT_RESOURCE_DIRS: tuple[str | _admin_base.Traversable, ...] = ("change-agent",)
_OVERRIDES_REL = ".ai-harness/overrides.json"


# ---------------------------------------------------------------------------
# Legacy deprecated entry points — kept importable so internal callers and
# external users have a migration window. Will be deleted in a future
# cleanup that drops the deprecated API entirely.
# ---------------------------------------------------------------------------


def render_agents(
    cli: AgentCli,
    names: list[str] | None = None,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> list[RenderedFile]:  # pragma: no cover - removed in next cleanup pass
    """DEPRECATED: use ``ADMINISTRATORS[cli].render_artifacts`` instead.

    Internal-only: kept so legacy callers can migrate to the administrator
    contract in their own time. Will be deleted once every internal caller
    migrates.
    """
    if names is None:
        names = _discover_agents()

    if overrides is None:
        overrides = _load_override_store(home if home is not None else Path.home())

    if cli == AgentCli.CLAUDE:
        return [_render_claude(name, overrides=overrides) for name in names]
    if cli == AgentCli.COPILOT:
        return [_render_copilot(name, overrides=overrides) for name in names]
    if cli == AgentCli.OPENCODE:
        return [_render_opencode(name, overrides=overrides) for name in names]
    return []


def get_agent_meta(name: str, overrides: dict | None = None, *, home: Path | None = None) -> dict:  # pragma: no cover
    """DEPRECATED: use ``ADMINISTRATORS[AgentCli.X].get_agent_metadata`` instead.

    Internal-only: kept so the wizard can migrate to the administrator
    metadata query in its own time.
    """
    meta = _AGENT_META.get(name)
    if meta is None:
        raise ValueError(f"Unknown agent template: {name!r}")
    if overrides is None:
        overrides = _load_override_store(home if home is not None else Path.home())
    override_entry = overrides.get(name, {})
    return _deep_merge(meta, override_entry)


def write_override_store(home: Path, payload: dict) -> None:  # pragma: no cover
    """DEPRECATED: use ``override_store.save_override_store`` instead."""
    existing = _load_override_store(home)
    merged = _deep_merge(existing, payload)
    path = home / _OVERRIDES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Legacy deprecated template metadata (Python dict — replaced by JSON metadata
# for the new admin path; kept for the deprecated ``get_agent_meta``).
# ---------------------------------------------------------------------------


_AGENT_META: dict[str, dict] = {
    "change-orchestrator": {
        "description": ("Change orchestrator — coordinates work via sub-agents; stays thin."),
        "mode": "primary",
        "model": {
            "opencode": "minimax/MiniMax-M3",
            "claude": "sonnet",
        },
        "permission": {
            "question": "allow",
            "task": {"*": "allow"},
            "bash": "allow",
            "edit": "allow",
            "read": "allow",
            "write": "allow",
        },
    },
    "change-explorer": {
        "description": (
            "Change explorer — read-only phase-1 investigator for file-backed changes. "
            "Estimates LOC budget, writes exploration.md, and reports affected files, plan, and risks."
        ),
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M2.7",
            "claude": "sonnet",
        },
    },
    "change-propose": {
        "description": "Change PRD author — writes prd.md in the sdd-propose structure without publishing anywhere.",
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M2.7",
            "claude": "sonnet",
        },
    },
    "change-design": {
        "description": "Change design author — writes design.md using the to-design deep-module structure.",
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M2.7",
            "claude": "sonnet",
        },
    },
    "change-specs": {
        "description": (
            "Change specs author — writes tracer-bullet specs from prd.md capabilities with RFC 2119 "
            "requirements and GIVEN/WHEN/THEN scenarios."
        ),
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M2.7",
            "claude": "sonnet",
        },
    },
    "change-tasks": {
        "description": (
            "Change task author — decomposes specs and design, then creates tasks through ai-harness task-create."
        ),
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M2.7",
            "claude": "sonnet",
        },
    },
    "change-implementor": {
        "description": (
            "Change implementor — drains file-backed tasks through task-next and task-done, "
            "making one commit per task on the current branch."
        ),
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M3",
            "claude": "sonnet",
        },
    },
    "change-validator": {
        "description": (
            "Change validator — read-only verdict-bearing reviewer that uses task-list, writes validation.md, "
            "and reports pass, pass-with-warnings, or fail with critical count."
        ),
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M2.7",
            "claude": "sonnet",
        },
    },
    "change-archiver": {
        "description": (
            "Change archiver — runs ai-harness change-archive for the target Change and commits "
            "the resulting .ai-harness archive/spec movement as a single scoped docs commit."
        ),
        "mode": "all",
        "model": {
            "opencode": "minimax/MiniMax-M2.7-highspeed",
            "claude": "sonnet",
        },
    },
}


# ---------------------------------------------------------------------------
# Legacy deprecated private helpers — self-contained so the legacy code path
# remains functional without depending on the new administrator package.
# These exist solely so ``render_agents`` / ``get_agent_meta`` /
# ``write_override_store`` keep working for the migration window.
# ---------------------------------------------------------------------------


def _load_override_store(home: Path) -> dict:
    """Legacy ``~/.ai-harness/overrides.json`` loader used by the deprecated entry points."""
    path = home / _OVERRIDES_REL
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict, override: dict) -> dict:
    """Legacy recursive merge used by :func:`get_agent_meta` and :func:`write_override_store`."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            result[key] = _deep_merge(base_value, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _get_agent_mode(
    name: str,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> str:
    """Legacy mode lookup used by :func:`render_agents` Claude dispatch."""
    return get_agent_meta(name, overrides=overrides, home=home).get("mode", "subagent")


# ---------------------------------------------------------------------------
# Legacy resource-discovery helpers — local duplicates of the canonical
# helpers in :mod:`ai_harness.modules.harness.administrators.base`. Kept
# here so test mocks targeting ``renderers._AGENT_RESOURCE_DIRS``,
# ``renderers.discover_agent_names``, etc. continue to work without
# touching every call site.
# ---------------------------------------------------------------------------


def _agent_resource_dirs() -> list[_admin_base.Traversable]:
    """Legacy resource-dir resolution used by :func:`_discover_agents`."""
    package_root = files("ai_harness.resources")
    roots: list[_admin_base.Traversable] = []
    for entry in _AGENT_RESOURCE_DIRS:
        root = package_root / entry if isinstance(entry, str) else entry
        if root.is_dir():
            roots.append(root)
    return roots


def _agent_template_files(root: _admin_base.Traversable) -> list[_admin_base.Traversable]:
    """Legacy visible-template filter used by :func:`_discover_agents`."""
    return sorted(
        (p for p in root.iterdir() if p.is_file() and p.name.endswith(".md") and not p.name.startswith("_")),
        key=lambda p: p.name,
    )


def _read_template_source(name: str) -> str:
    """Legacy template lookup used by :func:`_read_template_body`."""
    matches: list[_admin_base.Traversable] = []
    for root in _agent_resource_dirs():
        path = root / f"{name}.md"
        if path.is_file():
            matches.append(path)
    if len(matches) > 1:
        paths = ", ".join(str(path) for path in matches)
        raise ValueError(f"Duplicate agent template {name!r} found in: {paths}")
    if not matches:
        raise ValueError(f"Unknown agent template: {name!r}")
    return matches[0].read_text(encoding="utf-8")


def _discover_agents() -> list[str]:
    """Legacy change-agent discovery used by :func:`render_agents`."""
    names: list[str] = []
    seen: dict[str, str] = {}
    for root in _agent_resource_dirs():
        for p in _agent_template_files(root):
            name = Path(p.name).stem
            if name in seen:
                raise ValueError(f"Duplicate agent template {name!r} in {seen[name]} and {root}")
            seen[name] = str(root)
            names.append(name)
    return names


def load_agent_metadata(name: str) -> AgentMetadata:
    """Local copy of :func:`ai_harness...administrators.base.load_agent_metadata`.

    Kept here so mocks targeting ``renderers.load_agent_metadata`` (a
    pattern the test suite uses for the legacy code path) continue to
    affect calls within this module's deprecated entry points. The
    canonical implementation lives in the administrator subpackage; new
    code MUST use that one.
    """
    raw = _load_agent_metadata(name)
    return _decode_agent_metadata(raw, name=name)


def discover_agent_names() -> list[str]:
    """Local copy of :func:`ai_harness...administrators.base.discover_agent_names`.

    Kept here so mocks targeting ``renderers.discover_agent_names``
    continue to affect calls within this module's deprecated entry points.
    The canonical implementation lives in the administrator subpackage;
    new code MUST use that one.
    """
    return _discover_agents()


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Legacy deprecated per-CLI render helpers — produce ``RenderedFile``
# records for the deprecated ``render_agents`` entry point. The new
# administrator code in :mod:`ai_harness.modules.harness.administrators`
# owns the modern Artifact contract and the JSON metadata pipeline.
# ---------------------------------------------------------------------------


_CLAUDE_AGENTS_DIR = ".claude/agents"
_CLAUDE_SKILLS_DIR = ".claude/skills"
_COPILOT_AGENT_DIR = ".copilot/agents"
_OPENCODE_AGENT_DIR = ".config/opencode/agent"


def _render_opencode_agent(name: str, overrides: dict | None = None) -> RenderedFile:
    """Legacy OpenCode renderer used by :func:`_render_opencode`."""
    meta = get_agent_meta(name, overrides=overrides)
    body = _read_template_body(name)

    model_map = meta.get("model")
    if not isinstance(model_map, dict) or "opencode" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.opencode")

    opencode_frontmatter: dict[str, object] = {
        "description": meta.get("description", ""),
        "mode": meta.get("mode", "subagent"),
        "model": model_map["opencode"],
    }

    effort_map = meta.get("effort")
    if isinstance(effort_map, dict):
        opencode_effort = effort_map.get("opencode")
        if opencode_effort is not None:
            opencode_frontmatter["reasoningEffort"] = opencode_effort

    caps = meta.get("caps")
    explicit_permission = meta.get("permission")
    if isinstance(explicit_permission, dict):
        opencode_frontmatter["permission"] = explicit_permission
    elif isinstance(caps, AgentCaps):
        permission = _opencode_permission(caps)
        if permission:
            opencode_frontmatter["permission"] = permission

    if "color" in meta:
        opencode_frontmatter["color"] = meta["color"]

    yaml_text = _yaml_dump_frontmatter(opencode_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return RenderedFile(f"{name}.md", rendered)


def _render_claude_agent(name: str, overrides: dict | None = None) -> RenderedFile:
    """Legacy Claude subagent renderer used by :func:`_render_claude`."""
    meta = get_agent_meta(name, overrides=overrides)
    body = _read_template_body(name)

    model_map = meta.get("model")
    if not isinstance(model_map, dict) or "claude" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.claude")

    mode = meta.get("mode", "subagent")
    if mode == "primary":
        raise ValueError(f"Template {name}: mode=primary — use _render_claude_skill for the primary agent")

    claude_frontmatter: dict[str, object] = {
        "name": name,
        "description": meta.get("description", ""),
        "model": model_map["claude"],
    }

    effort_map = meta.get("effort")
    if isinstance(effort_map, dict):
        claude_effort = effort_map.get("claude")
        if claude_effort is not None:
            claude_frontmatter["effort"] = claude_effort

    caps = meta.get("caps")
    if isinstance(caps, AgentCaps) and caps != AgentCaps():
        claude_frontmatter["tools"] = ", ".join(_claude_tools(caps))

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return RenderedFile(f"{name}.md", rendered)


def _render_claude_skill(name: str, overrides: dict | None = None) -> RenderedFile:
    """Legacy Claude primary-skill renderer used by :func:`_render_claude`."""
    meta = get_agent_meta(name, overrides=overrides)
    body = _read_template_body(name)

    model_map = meta.get("model")
    if not isinstance(model_map, dict) or "claude" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.claude")

    mode = meta.get("mode", "subagent")
    if mode != "primary":
        raise ValueError(f"Template {name}: mode must be primary for a skill, got {mode!r}")

    claude_frontmatter: dict[str, object] = {
        "description": meta.get("description", ""),
    }
    spawn_note = ""
    caps = meta.get("caps")
    if isinstance(caps, AgentCaps) and caps.spawn:
        names = ", ".join(f"`{a}`" for a in caps.spawn)
        spawn_note = (
            "\n\n## Subagent spawn allowlist\n\n"
            "Claude skills cannot enforce spawn restrictions in frontmatter. "
            "The following prose constraint replaces the OpenCode "
            f"``permission.task`` allowlist:\n\n"
            f"Only spawn these subagents: {names}.\n"
        )

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}{spawn_note}"
    return RenderedFile("SKILL.md", rendered)


def _render_claude(
    name: str,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> RenderedFile:
    """Legacy Claude dispatch used by :func:`render_agents`."""
    if _get_agent_mode(name, overrides=overrides, home=home) == "primary":
        rendered = _render_claude_skill(name, overrides=overrides)
        return RenderedFile(f"{_CLAUDE_SKILLS_DIR}/{name}/{rendered.filename}", rendered.content)
    rendered = _render_claude_agent(name, overrides=overrides)
    return RenderedFile(f"{_CLAUDE_AGENTS_DIR}/{rendered.filename}", rendered.content)


def _render_opencode(name: str, overrides: dict | None = None) -> RenderedFile:
    """Legacy OpenCode dispatch used by :func:`render_agents`."""
    rendered = _render_opencode_agent(name, overrides=overrides)
    return RenderedFile(f"{_OPENCODE_AGENT_DIR}/{rendered.filename}", rendered.content)


def _render_copilot_agent(name: str, overrides: dict | None = None) -> RenderedFile:
    """Legacy Copilot renderer used by :func:`_render_copilot`."""
    meta = get_agent_meta(name, overrides=overrides)
    body = _read_template_body(name)

    copilot_frontmatter: dict[str, object] = {
        "name": name,
        "description": meta.get("description", ""),
    }

    yaml_text = _yaml_dump_frontmatter(copilot_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return RenderedFile(f"{name}.agent.md", rendered)


def _render_copilot(
    name: str,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> RenderedFile:
    """Legacy Copilot dispatch used by :func:`render_agents`."""
    rendered = _render_copilot_agent(name, overrides=overrides)
    return RenderedFile(f"{_COPILOT_AGENT_DIR}/{rendered.filename}", rendered.content)
