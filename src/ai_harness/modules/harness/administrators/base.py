"""Provider-administrator base — public types and shared private helpers.

This subpackage (:mod:`ai_harness.modules.harness.administrators`) is the deep
seam of the harness: callers select an administrator by ``AgentCli`` and
receive installable :class:`Artifact` records without knowing about provider
discovery, override merging, frontmatter shape, or install-path layout.

Layout
------
``base`` owns the public types (``Artifact``, ``AgentMetadata``, ``AgentCaps``,
``ArtifactsAdministrator``) and every private helper that more than one
provider file consumes. Each provider file (``claude``, ``opencode``,
``copilot``) owns its own concrete administrator plus the per-provider private
helpers (``_claude_tools``, ``_opencode_permission``). Providers MUST NOT
import from each other — every cross-provider detail belongs here.

Public surface (re-exported from :mod:`ai_harness.modules.harness.administrators`)
---------------------------------------------------------------------------------
Artifact                          One rendered install artifact: home-relative
                                  POSIX path and full file content.
AgentMetadata                     Decoded ``agent-metadata/<name>.json`` content.
AgentCaps                         CLI-neutral capability flags.
ArtifactsAdministrator            Abstract base class — the contract every
                                  provider administrator implements.
load_agent_metadata               Read and decode ``agent-metadata/<name>.json``.
discover_agent_names              Visible change-agent templates in sorted order.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal

import yaml

from ai_harness.modules.harness.override_store import deep_merge, load_override_store

__all__ = [
    "AgentCaps",
    "AgentMetadata",
    "Artifact",
    "ArtifactsAdministrator",
    "discover_agent_names",
    "load_agent_metadata",
]

# ---------------------------------------------------------------------------
# Resource-discovery constants
# ---------------------------------------------------------------------------

_AGENT_RESOURCE_DIRS: tuple[str | Traversable, ...] = ("change-agent",)

_ALLOWED_METADATA_KEYS: frozenset[str] = frozenset(
    {"description", "mode", "model", "effort", "caps", "permission", "color"}
)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AgentCaps:
    """What an agent may do, in CLI-neutral terms. Reading files is always
    allowed; these gate the rest. Each renderer translates *from* this — no
    single CLI's permission schema is the canonical form.

    ``write`` collapses OpenCode's edit+write into one knob: in practice an
    agent is either allowed to touch the filesystem or not. Split into two
    fields only if an agent ever needs to edit existing files but not create
    new ones.
    """

    write: bool = True  # may modify the filesystem (edit + create)
    bash: bool = True  # may run shell commands
    spawn: tuple[str, ...] | None = None  # None = cannot spawn; tuple = subagent allowlist


@dataclass(frozen=True, slots=True)
class Artifact:
    """One rendered install artifact: a home-relative path and the full file content.

    Every administrator's ``render_artifacts`` returns a list of ``Artifact``
    objects. Callers write each artifact to ``home / artifact.install_path``
    using ``artifact.content`` — the provider-owned path and the
    provider-rendered content, with no provider-specific branching required.
    """

    install_path: str
    content: str


@dataclass(frozen=True, slots=True)
class AgentMetadata:
    """Decoded ``agent-metadata/<name>.json`` content.

    * ``description`` — required string from the JSON resource.
    * ``mode`` — provider-meaning string (``"primary"`` routes Claude to a skill;
      other values pass through as Claude/OpenCode ``mode``; Copilot ignores it).
    * ``model`` — provider-keyed model map. ``model.claude`` is required for
      Claude rendering; ``model.opencode`` is required for OpenCode rendering;
      Copilot requires no model.
    * ``effort`` — provider-keyed effort map. Values are strings or ``None``;
      ``None`` means "drop the field" and MUST omit the frontmatter key.
    * ``caps`` — typed capability flags translated to provider permission/tool
      schemas. Defaults to :class:`AgentCaps` (no restrictions).
    * ``permission`` — raw OpenCode permission block, only honored when the
      OpenCode administrator renders. ``None`` means "derive from caps".
    * ``color`` — OpenCode color passthrough (hex or named). Optional.
    """

    description: str
    mode: str = "subagent"
    model: Mapping[str, str] = field(default_factory=dict)
    effort: Mapping[str, str | None] = field(default_factory=dict)
    caps: AgentCaps = field(default_factory=AgentCaps)
    permission: Mapping[str, object] | None = None
    color: str | None = None


class ArtifactsAdministrator(ABC):
    """Provider administrator contract.

    Each concrete administrator owns template discovery, JSON metadata
    loading, override-store reading/merging, provider-specific frontmatter
    generation, and the provider's install-path layout. Callers select
    ``ADMINISTRATORS[AgentCli.X]`` and call this shared contract; they do
    not branch on provider internals.

    Implementations MUST raise :class:`ValueError` for unknown agent names,
    duplicate template names, missing metadata, invalid metadata, and
    missing provider model values.

    Subclasses set the ``provider`` class attribute to one of
    ``"claude" | "opencode" | "copilot"`` so test assertions and runtime
    introspection can identify the administrator without isinstance checks.
    """

    provider: Literal["claude", "opencode", "copilot"]

    @abstractmethod
    def render_artifacts(
        self,
        names: list[str] | None = None,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> list[Artifact]:
        """Render the named change agents to installable artifacts.

        *names* defaults to all discovered agents when ``None``; pass an
        explicit list to render a subset in the order given. *overrides*
        follows the documented contract: ``None`` reads the override store
        from ``home/.ai-harness/overrides.json`` (default ``Path.home()``);
        ``{}`` is an explicit no-disk-read path; any other dict is used
        verbatim.

        Returns artifacts in the discovered/requested order so the install
        path is stable and the install manifest is deterministic.
        """

    def get_agent_metadata(
        self,
        name: str,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> AgentMetadata:
        """Return the decoded metadata for *name* with overrides applied.

        The override semantics match :meth:`render_artifacts`: ``None``
        reads disk, ``{}`` skips the disk read, and explicit dicts are
        used verbatim. The returned ``AgentMetadata`` is a fresh value
        callers may inspect or mutate without affecting shared state.

        Default implementation on the base class — providers inherit
        this unless they need provider-specific override handling.
        Delegates to the shared :func:`_resolve_agent_metadata` helper
        so every administrator resolves metadata identically.
        """
        return _resolve_agent_metadata(name, overrides=overrides, home=home)

    def discover_agent_names(self) -> list[str]:
        """Return visible change-agent names in sorted filename order.

        ``_``-prefixed templates are excluded; duplicates fail loudly.
        The returned list is the install/manifest ordering authority.

        Default implementation on the base class — providers inherit
        this because template discovery is provider-agnostic and every
        administrator reads the same template set from
        :func:`discover_agent_names`.
        """
        return discover_agent_names()


# ---------------------------------------------------------------------------
# Shared private helpers — used by every provider admin. Treat these as
# intra-package seams; tests reach in to assert behavior, callers do not.
# ---------------------------------------------------------------------------


def _yaml_dump_frontmatter(data: dict[str, object]) -> str:
    """Deterministic YAML dump for frontmatter blocks.

    Key order is preserved as-is so that nested ``permission`` blocks and
    similar structures emit in the order declared by the rendering admin —
    callers put things in the order they want shown on disk.
    """
    return yaml.dump(
        data,
        sort_keys=False,
        default_flow_style=False,
        explicit_start=False,
        explicit_end=False,
        allow_unicode=True,
    ).rstrip("\n")


def _read_template_source(name: str) -> str:
    """Return the raw template text for a named agent (e.g. ``"explorer"``)."""
    matches: list[Traversable] = []
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


def _read_template_body(name: str) -> str:
    """Return the prompt body for a named agent (full template text — no frontmatter)."""
    return _read_template_source(name)


def _agent_resource_dirs() -> list[Traversable]:
    """Return existing agent resource directories in render order."""
    package_root = files("ai_harness.resources")
    roots: list[Traversable] = []
    for entry in _AGENT_RESOURCE_DIRS:
        root = package_root / entry if isinstance(entry, str) else entry
        if root.is_dir():
            roots.append(root)
    return roots


def _agent_template_files(root: Traversable) -> list[Traversable]:
    """Return visible markdown template files from *root* in stable order."""
    return sorted(
        (p for p in root.iterdir() if p.is_file() and p.name.endswith(".md") and not p.name.startswith("_")),
        key=lambda p: p.name,
    )


def _agent_metadata_root() -> Traversable:
    """Return the ``agent-metadata/`` resource directory."""
    return files("ai_harness.resources") / "agent-metadata"


def _load_agent_metadata(name: str) -> dict:
    """Read ``agent-metadata/<name>.json`` via importlib.resources.

    Returns the parsed JSON dict. Raises :class:`ValueError` if the file
    is missing — the resource layout is the contract, and a template
    without metadata is drift that must surface at install time.
    """
    path = _agent_metadata_root() / f"{name}.json"
    if not path.is_file():
        raise ValueError(f"Missing agent metadata for {name!r}: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_metadata_schema(raw: dict, *, filename: str) -> None:
    """Reject unknown fields, missing description, and wrong top-level types.

    Raises :class:`ValueError` naming the file and offending field so the
    failure is debuggable from a single log line. Inner-field validation
    (model/effort shape, permission type, etc.) is delegated to the
    individual decoders.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{filename}: metadata top-level must be an object, got {type(raw).__name__}")
    unknown = set(raw) - _ALLOWED_METADATA_KEYS
    if unknown:
        raise ValueError(f"{filename}: unknown metadata field(s) {sorted(unknown)!r}")
    if "description" not in raw:
        raise ValueError(f"{filename}: missing required 'description' field")
    if not isinstance(raw["description"], str):
        raise ValueError(f"{filename}: 'description' must be a string, got {type(raw['description']).__name__}")
    if "mode" in raw and not isinstance(raw["mode"], str):
        raise ValueError(f"{filename}: 'mode' must be a string, got {type(raw['mode']).__name__}")


def _decode_agent_caps(raw: object, *, filename: str) -> AgentCaps:
    """Decode a ``caps`` JSON value into a typed :class:`AgentCaps`.

    ``None``/missing → :class:`AgentCaps` defaults. A non-dict raises
    :class:`ValueError` naming the file.
    """
    if raw is None:
        return AgentCaps()
    if not isinstance(raw, dict):
        raise ValueError(f"{filename}: 'caps' must be an object, got {type(raw).__name__}")
    write = raw.get("write", True)
    bash = raw.get("bash", True)
    spawn_raw = raw.get("spawn", None)
    if not isinstance(write, bool):
        raise ValueError(f"{filename}: 'caps.write' must be a bool, got {type(write).__name__}")
    if not isinstance(bash, bool):
        raise ValueError(f"{filename}: 'caps.bash' must be a bool, got {type(bash).__name__}")
    if spawn_raw is None:
        spawn: tuple[str, ...] | None = None
    elif isinstance(spawn_raw, list):
        if not all(isinstance(item, str) for item in spawn_raw):
            raise ValueError(f"{filename}: 'caps.spawn' entries must all be strings")
        spawn = tuple(spawn_raw)
    else:
        raise ValueError(f"{filename}: 'caps.spawn' must be null or array of strings, got {type(spawn_raw).__name__}")
    return AgentCaps(write=write, bash=bash, spawn=spawn)


def _decode_effort_map(raw: object, *, filename: str) -> Mapping[str, str | None]:
    """Decode the ``effort`` JSON value into a provider-keyed mapping.

    Each value MUST be either a string or ``null`` — JSON ``null`` is the
    documented "drop the field" sentinel that the per-provider
    administrators translate into "omit the provider frontmatter key".
    Other types fail loudly.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{filename}: 'effort' must be an object, got {type(raw).__name__}")
    decoded: dict[str, str | None] = {}
    for provider, value in raw.items():
        if value is None or isinstance(value, str):
            decoded[provider] = value
        else:
            raise ValueError(f"{filename}: 'effort.{provider}' must be string or null, got {type(value).__name__}")
    return decoded


def _decode_model_map(raw: object, *, filename: str) -> Mapping[str, str]:
    """Decode the ``model`` JSON value into a provider-keyed string map.

    Each value MUST be a string; non-string values fail loudly so
    silent model coercion never reaches a provider renderer.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{filename}: 'model' must be an object, got {type(raw).__name__}")
    decoded: dict[str, str] = {}
    for provider, value in raw.items():
        if not isinstance(value, str):
            raise ValueError(f"{filename}: 'model.{provider}' must be a string, got {type(value).__name__}")
        decoded[provider] = value
    return decoded


def _decode_permission(raw: object, *, filename: str) -> Mapping[str, object] | None:
    """Decode the raw ``permission`` JSON value (only used for OpenCode)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{filename}: 'permission' must be an object, got {type(raw).__name__}")
    return raw


def _decode_agent_metadata(raw: dict, *, name: str) -> AgentMetadata:
    """Decode a single agent metadata JSON dict into :class:`AgentMetadata`.

    Runs the schema validator and the per-field decoders in one place so
    :class:`AgentMetadata` construction stays atomic — partial state
    cannot leak out of this function. *name* is passed separately so the
    raw dict stays untouched and the schema validator can reject any
    unexpected keys cleanly.
    """
    filename = f"agent-metadata/{name}.json"
    _validate_metadata_schema(raw, filename=filename)
    return AgentMetadata(
        description=raw["description"],
        mode=raw.get("mode", "subagent"),
        model=_decode_model_map(raw.get("model"), filename=filename),
        effort=_decode_effort_map(raw.get("effort"), filename=filename),
        caps=_decode_agent_caps(raw.get("caps"), filename=filename),
        permission=_decode_permission(raw.get("permission"), filename=filename),
        color=raw.get("color") if isinstance(raw.get("color"), str) else None,
    )


def load_agent_metadata(name: str) -> AgentMetadata:
    """Public loader: read ``agent-metadata/<name>.json`` and decode it.

    Combines ``_load_agent_metadata`` with ``_decode_agent_metadata``
    so callers get a fully-typed :class:`AgentMetadata` from a single
    call. The decoder is strict: unknown fields, missing description,
    wrong types, and missing metadata all raise :class:`ValueError`.
    """
    raw = _load_agent_metadata(name)
    return _decode_agent_metadata(raw, name=name)


def _discover_agents() -> list[str]:
    """Return list of agent template names (without ``.md`` extension) in resource-set order.

    Files whose name starts with ``_`` are excluded — they are bundled
    resources, not agents.
    """
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


def discover_agent_names() -> list[str]:
    """Return the visible change-agent template names in sorted order.

    Walks ``change-agent/*.md`` via importlib.resources, sorts by
    filename, and excludes ``_``-prefixed templates (which are bundled
    resources, not agents). Duplicate template names across the resource
    set fail loudly with :class:`ValueError`.

    The returned order is the canonical install order: it is the order
    rendered agents appear on disk and the order recorded in the install
    manifest. Templates without matching metadata, or metadata without a
    visible template, are caught by the administrators'
    :meth:`render_artifacts` calls — this function returns the template
    set as the source of truth.
    """
    return _discover_agents()


def _agent_caps_to_dict(caps: AgentCaps) -> dict:
    """Serialize :class:`AgentCaps` to a plain dict for override merging.

    Round-trips through :func:`_decode_agent_caps` so merged override
    payloads land back in the typed dataclass.
    """
    return {"write": caps.write, "bash": caps.bash, "spawn": list(caps.spawn) if caps.spawn else None}


def _resolve_agent_metadata(
    name: str,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> AgentMetadata:
    """Resolve *name*'s metadata with the override-store semantics.

    ``overrides=None`` reads the shared override store from
    ``home/.ai-harness/overrides.json`` (default ``Path.home()``); ``{}``
    is an explicit no-disk-read path; any other dict is used verbatim.
    The resolved metadata is returned as a fresh :class:`AgentMetadata`
    so callers cannot mutate the shared template state.
    """
    if overrides is None:
        overrides = load_override_store(home if home is not None else Path.home())

    base = load_agent_metadata(name)
    entry = overrides.get(name, {})
    if not entry:
        return base

    base_dict: dict = {
        "description": base.description,
        "mode": base.mode,
        "model": dict(base.model),
        "effort": dict(base.effort),
        "caps": _agent_caps_to_dict(base.caps),
        "permission": dict(base.permission) if base.permission is not None else None,
        "color": base.color,
    }
    merged = deep_merge(base_dict, entry)
    # Re-decode through the schema validator so the merged value is
    # type-safe and any override drift surfaces as ValueError here.
    return _decode_agent_metadata(merged, name=name)
