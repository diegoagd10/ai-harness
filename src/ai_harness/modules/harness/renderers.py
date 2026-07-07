"""Per-provider agent renderers — transform a CLI-neutral agent template into a native agent file.

Each render function takes a template name and returns the rendered string with
CLI-specific frontmatter injected from code constants. Resource template files
contain only the shared prompt body — all metadata (description, mode, model,
permissions) lives in ``_AGENT_META``.

Public surface
--------------
AgentCaps              What an agent may do, in CLI-neutral terms.
RenderedFile           One rendered agent file: a home-relative path and the file's full content.
render_agents          Render change agents for a CLI as home-relative ``RenderedFile`` records.
get_agent_meta         Return the metadata dict for a named agent.
write_override_store   Deep-merge into the per-agent override store at ``~/.ai-harness/overrides.json``.

All other render mechanics (per-CLI render functions, discovery, mode dispatch,
destination layout) are private and owned by ``render_agents``.
"""

from __future__ import annotations

import copy
import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Literal, NamedTuple

import yaml

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
    "RenderedFile",
    "discover_agent_names",
    "get_agent_meta",
    "load_agent_metadata",
    "render_agents",
    "write_override_store",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AGENT_RESOURCE_DIRS: tuple[str | Traversable, ...] = ("change-agent",)

_OVERRIDES_REL = ".ai-harness/overrides.json"


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class RenderedFile(NamedTuple):
    """One rendered agent file: a home-relative path and the file's full content.

    Every renderer in this module returns a ``RenderedFile`` so callers can
    read ``.filename`` and ``.content`` without remembering positional order.
    The single public entry :func:`render_agents` yields a list of these.
    """

    filename: str
    content: str


# Agent metadata — single source of truth for description, mode, per-CLI
# models, and permission blocks. Resource templates carry only the prompt
# body; ``_AGENT_META`` is what the render functions read.


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


# ---------------------------------------------------------------------------
# Public types — provider-administrator contract.
#
# These four types are the load-bearing seam of the new architecture:
#
# - ``Artifact`` is the rendered output of every administrator — home-relative
#   POSIX path plus full file content. It replaces the old ``RenderedFile``
#   abstraction so operations can write ``home / artifact.install_path``
#   without knowing the provider's directory layout.
#
# - ``AgentMetadata`` is the decoded, typed representation of one
#   ``agent-metadata/<name>.json`` resource. Concrete administrators receive
#   a parsed ``AgentMetadata`` and translate it into provider-specific
#   frontmatter and install paths.
#
# - ``ArtifactsAdministrator`` is the abstract base class that locks the
#   three public methods administrators expose. Each provider implements
#   these with its own discovery, metadata loading, override merging,
#   frontmatter shape, and path layout.
#
# - ``ADMINISTRATORS`` is the dispatch table keyed by ``AgentCli``. Callers
#   select an administrator once and then call the shared contract
#   polymorphically — no per-provider branching in operations or the wizard.
# ---------------------------------------------------------------------------


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
      schemas. Defaults to ``AgentCaps()`` (no restrictions).
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

    @abstractmethod
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
        """

    @abstractmethod
    def discover_agent_names(self) -> list[str]:
        """Return visible change-agent names in sorted filename order.

        ``_``-prefixed templates are excluded; duplicates fail loudly.
        The returned list is the install/manifest ordering authority.
        """


class ClaudeArtifactsAdministrator(ArtifactsAdministrator):
    """Claude provider administrator — owns Claude frontmatter and install paths.

    Hides the Claude skill-vs-agent mode dispatch, the ``.claude/skills/...``
    and ``.claude/agents/...`` install-path layout, the model/effort/tools
    frontmatter shape, and the spawn-allowlist prose injection for primary
    skills. Callers select this administrator and call
    :meth:`render_artifacts` polymorphically — no per-provider branching
    in operations or the wizard.
    """

    provider: Literal["claude", "opencode", "copilot"] = "claude"

    def render_artifacts(
        self,
        names: list[str] | None = None,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> list[Artifact]:
        """Render Claude change agents to installable artifacts."""
        resolved_names = list(names) if names is not None else self.discover_agent_names()
        artifacts: list[Artifact] = []
        for name in resolved_names:
            metadata = self.get_agent_metadata(name, overrides=overrides, home=home)
            if metadata.mode == "primary":
                artifacts.append(_render_claude_skill_artifact(name, metadata))
            else:
                artifacts.append(_render_claude_agent_artifact(name, metadata))
        return artifacts

    def get_agent_metadata(
        self,
        name: str,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> AgentMetadata:
        """Return Claude-resolved metadata for *name* with overrides applied."""
        return _resolve_agent_metadata(name, overrides=overrides, home=home)

    def discover_agent_names(self) -> list[str]:
        # Discovery is provider-agnostic — all administrators see the same
        # visible template set. Tasks 5/6/7 keep this delegation intact.
        return discover_agent_names()


class OpenCodeArtifactsAdministrator(ArtifactsAdministrator):
    """OpenCode provider administrator — owns OpenCode frontmatter and install paths.

    Hides the ``.config/opencode/agent/<name>.md`` install path, the
    permission derivation from :class:`AgentCaps`, the explicit
    ``permission`` precedence over caps-derived permission, the
    ``reasoningEffort`` mapping from ``effort.opencode``, the color
    passthrough, and the ``mode`` passthrough. Callers select this
    administrator and call :meth:`render_artifacts` polymorphically.
    """

    provider: Literal["claude", "opencode", "copilot"] = "opencode"

    def render_artifacts(
        self,
        names: list[str] | None = None,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> list[Artifact]:
        """Render OpenCode change agents to installable artifacts."""
        resolved_names = list(names) if names is not None else self.discover_agent_names()
        artifacts: list[Artifact] = []
        for name in resolved_names:
            metadata = self.get_agent_metadata(name, overrides=overrides, home=home)
            artifacts.append(_render_opencode_agent_artifact(name, metadata))
        return artifacts

    def get_agent_metadata(
        self,
        name: str,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> AgentMetadata:
        """Return OpenCode-resolved metadata for *name* with overrides applied."""
        return _resolve_agent_metadata(name, overrides=overrides, home=home)

    def discover_agent_names(self) -> list[str]:
        return discover_agent_names()


class CopilotArtifactsAdministrator(ArtifactsAdministrator):
    """Copilot provider administrator — stub populated in task 7."""

    provider: Literal["claude", "opencode", "copilot"] = "copilot"

    def render_artifacts(
        self,
        names: list[str] | None = None,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> list[Artifact]:
        raise NotImplementedError("CopilotArtifactsAdministrator.render_artifacts lands in task 7")

    def get_agent_metadata(
        self,
        name: str,
        overrides: dict | None = None,
        *,
        home: Path | None = None,
    ) -> AgentMetadata:
        raise NotImplementedError("CopilotArtifactsAdministrator.get_agent_metadata lands in task 7")

    def discover_agent_names(self) -> list[str]:
        return discover_agent_names()


# Dispatch table — populated with one administrator per supported CLI.
# Generic has no administrator; callers that need generic behavior should
# use ``ADMINISTRATORS.get(AgentCli.GENERIC)`` and treat absence as a no-op.
ADMINISTRATORS: dict[AgentCli, ArtifactsAdministrator] = {
    AgentCli.CLAUDE: ClaudeArtifactsAdministrator(),
    AgentCli.OPENCODE: OpenCodeArtifactsAdministrator(),
    AgentCli.COPILOT: CopilotArtifactsAdministrator(),
}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def render_agents(
    cli: AgentCli,
    names: list[str] | None = None,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> list[RenderedFile]:
    """Render the change agents for *cli* as home-relative ``RenderedFile`` records.

    The sole public agent-render entry. Owns skill-vs-agent mode dispatch,
    destination directory layout, and filename. Returns POSIX home-relative
    paths in discovery (sorted) order so output is byte-identical to the prior
    inline emission.

    *names* defaults to the discovered change agents; pass an explicit list to
    render a subset. *overrides* is an optional per-agent partial overlay
    deep-merged over the template defaults; ``None`` loads the override
    store from ``home/.ai-harness/overrides.json`` (default
    ``Path.home()``), ``{}`` is an explicit no-op. CLIs without native
    agent support return an empty list.
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


def get_agent_meta(name: str, overrides: dict | None = None, *, home: Path | None = None) -> dict:
    """Return the metadata dict for a named agent (from ``_AGENT_META``).

    *overrides* is an optional per-agent partial overlay (see project docs).
    When ``None`` (the default), the override store is loaded from
    ``home/.ai-harness/overrides.json`` (``Path.home()`` when *home* is
    ``None``); an absent file is a no-op, a malformed file raises
    ``json.JSONDecodeError``. When provided, the dict is used verbatim —
    callers can pass ``{}`` for an explicit empty store, sidestepping the
    disk lookup. The override entry for *name* is deep-merged over the
    template defaults; absent or unknown agents keep their template values.
    The returned dict is always a fresh copy so callers cannot mutate the
    shared template state.

    Public so tests can derive expected frontmatter from the same source.
    """
    meta = _AGENT_META.get(name)
    if meta is None:
        raise ValueError(f"Unknown agent template: {name!r}")
    if overrides is None:
        overrides = _load_override_store(home if home is not None else Path.home())
    override_entry = overrides.get(name, {})
    return _deep_merge(meta, override_entry)


def write_override_store(home: Path, payload: dict) -> None:
    """Deep-merge *payload* into the per-agent override store and write it back.

    Public so the ``set-models`` wizard can persist user choices without
    re-implementing the store path. Existing entries for other agents, or
    for the same agent under different fields, are preserved — only the
    keys present in *payload* change. The file is written atomically: an
    in-memory merge, then a single write to ``~/.ai-harness/overrides.json``.
    Malformed existing JSON is raised as-is (matching the loader's contract).
    """
    existing = _load_override_store(home)
    merged = _deep_merge(existing, payload)
    path = home / _OVERRIDES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _opencode_permission(caps: AgentCaps) -> dict:
    """Translate caps into OpenCode's ``permission`` block.

    Only deviations from OpenCode's allow-by-default are emitted, so a
    full-capability agent yields ``{}`` (no permission block).
    """
    perm: dict = {}
    if not caps.write:
        perm["edit"] = "deny"
        perm["write"] = "deny"
    if not caps.bash:
        perm["bash"] = "deny"
    if caps.spawn is not None:
        perm["task"] = {"*": "deny", **{name: "allow" for name in caps.spawn}}
    return perm


# ponytail: Claude's ``tools`` is a closed allow-list — set it and the agent
# gets ONLY these, nothing else. So this translation is necessarily coarse:
# it expresses "restricted minimal set" vs "everything" (omit tools), not
# fine-grained subtractions from Claude's full toolset. ``spawn`` is not
# reflected here — every spawn-capable agent is mode=primary and renders via
# _render_claude_skill, never the agent renderer.
def _claude_tools(caps: AgentCaps) -> list[str]:
    """Translate caps into a Claude ``tools`` allow-list."""
    tools = ["Read", "Grep", "Glob"]
    if caps.write:
        tools += ["Edit", "Write"]
    if caps.bash:
        tools.append("Bash")
    return tools


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


def _load_override_store(home: Path) -> dict:
    """Return the per-agent override store at ``home/.ai-harness/overrides.json``.

    Returns ``{}`` when the file is missing (no-op override). Malformed JSON
    is raised as-is so the user can fix it instead of silently rendering
    template defaults. Owned here — next to the merge logic that consumes
    it — so the operations layer doesn't need to know about the store path.
    """
    path = home / _OVERRIDES_REL
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _deep_merge(base: dict, override: dict) -> dict:
    """Return a fresh dict with *override* recursively merged over *base*.

    Dicts merge key-by-key (recursively); scalars and lists in *override*
    replace those in *base*. The original *base* is never mutated; the
    returned dict (and any nested dicts inside it) are fresh copies.
    """
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
    """Return the mode (subagent|primary) for a named agent.

    Threads *overrides* and *home* through to :func:`get_agent_meta` so the
    mode lookup shares the same resolution path as the frontmatter pass — an
    explicit ``overrides=`` arg (including ``{}``) must NOT fall through to a
    ``~/.ai-harness/overrides.json`` read at the ambient ``$HOME``.
    """
    return get_agent_meta(name, overrides=overrides, home=home).get("mode", "subagent")


def _discover_agents() -> list[str]:
    """Return list of agent template names (without .md extension) in resource-set order.

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


def _read_template_source(name: str) -> str:
    """Return the raw template text for a named agent (e.g. 'explorer')."""
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


def _yaml_dump_frontmatter(data: dict[str, object]) -> str:
    """Deterministic YAML dump for frontmatter blocks.

    Key order is preserved as-is so that nested ``permission`` blocks and
    similar structures emit in the order declared by ``_AGENT_META`` —
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


# ---------------------------------------------------------------------------
# Render functions — each builds CLI-specific frontmatter from _AGENT_META
# and concatenates it with the shared template body.
# ---------------------------------------------------------------------------


def _render_opencode_agent(name: str, overrides: dict | None = None) -> RenderedFile:
    """Render a change agent template into an OpenCode agent file.

    Returns a :class:`RenderedFile` whose ``filename`` is ``<name>.md`` and
    whose ``content`` is the full rendered frontmatter + body.

    Raises ValueError if the agent's metadata lacks ``model.opencode``.
    """
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

    # Emit effort as OpenCode's ``reasoningEffort`` only when configured for this CLI.
    # ``None`` means the wizard deliberately cleared a stale override (e.g. when
    # switching to a non-reasoning model); rendering that as ``null`` would
    # leave stale frontmatter on disk, so we treat ``None`` the same as unset.
    effort_map = meta.get("effort")
    if isinstance(effort_map, dict):
        opencode_effort = effort_map.get("opencode")
        if opencode_effort is not None:
            opencode_frontmatter["reasoningEffort"] = opencode_effort

    # Translate caps into OpenCode's permission block (omitted when empty).
    # An explicit ``meta["permission"]`` overrides the caps-derived block —
    # used by orchestrator where the desired stance is permissive rather
    # than deny-by-default.
    caps = meta.get("caps")
    explicit_permission = meta.get("permission")
    if isinstance(explicit_permission, dict):
        opencode_frontmatter["permission"] = explicit_permission
    elif isinstance(caps, AgentCaps):
        permission = _opencode_permission(caps)
        if permission:
            opencode_frontmatter["permission"] = permission

    # Pass through color if present — OpenCode accepts a hex value or one of
    # primary, secondary, accent, success, warning, error, info.
    if "color" in meta:
        opencode_frontmatter["color"] = meta["color"]

    yaml_text = _yaml_dump_frontmatter(opencode_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return RenderedFile(f"{name}.md", rendered)


def _render_claude_agent(name: str, overrides: dict | None = None) -> RenderedFile:
    """Render a change agent template into a Claude Code agent file.

    Returns a :class:`RenderedFile` whose ``filename`` is ``<name>.md`` and
    whose ``content`` is the full rendered frontmatter + body.

    Raises ValueError if the agent lacks ``model.claude`` or has ``mode: primary``.
    """
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

    # Emit effort as Claude's ``effort`` only when configured for this CLI.
    # ``None`` means the wizard deliberately cleared a stale override; rendering
    # that as ``null`` would leave stale frontmatter on disk, so we treat
    # ``None`` the same as unset.
    effort_map = meta.get("effort")
    if isinstance(effort_map, dict):
        claude_effort = effort_map.get("claude")
        if claude_effort is not None:
            claude_frontmatter["effort"] = claude_effort

    # Emit a Claude tools allow-list only when caps restrict the agent; a
    # full-capability agent omits `tools` entirely (which means "all tools").
    caps = meta.get("caps")
    if isinstance(caps, AgentCaps) and caps != AgentCaps():
        claude_frontmatter["tools"] = ", ".join(_claude_tools(caps))

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return RenderedFile(f"{name}.md", rendered)


def _render_claude_skill(name: str, overrides: dict | None = None) -> RenderedFile:
    """Render the primary change agent template into a Claude Code skill file.

    Returns a :class:`RenderedFile` whose ``filename`` is ``SKILL.md`` and
    whose ``content`` is the full rendered frontmatter + body.

    The skill carries only ``description`` in frontmatter — no model, effort,
    or tools. Overrides are intentionally ignored: skills run on the session
    model and inherit the user's effort setting.

    Raises ValueError if the agent lacks ``model.claude`` or has mode other than ``primary``.
    """
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
    # No name field — skills aren't spawned by name.
    # No model field — skills run on the session model.
    # No effort field — skills inherit the user's session effort setting.
    # No tools field — unrestricted.
    # No mode field — Claude has no mode concept; skill-vs-agent is determined
    # by destination directory, not frontmatter.
    # No agents/permission field — Claude skills cannot carry an agents
    # allowlist in frontmatter (the Claude skill spec has no ``agents``
    # key). The OpenCode ``permission.task`` spawn allowlist is therefore
    # rendered as a prose constraint injected into the body below.

    # Inject the spawn allowlist as a prose section — Claude skills have no
    # frontmatter field to restrict subagent spawning, so we convert
    # permission.task into a conversational constraint.
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


# ---------------------------------------------------------------------------
# Agent-render seam — per-CLI dispatch helpers that own skill-vs-agent mode
# dispatch, destination directory layout, and filename.  Callers state the
# CLI; they never assemble paths themselves.
# ---------------------------------------------------------------------------

_CLAUDE_AGENTS_DIR = ".claude/agents"
_CLAUDE_SKILLS_DIR = ".claude/skills"
_COPILOT_AGENT_DIR = ".copilot/agents"
_OPENCODE_AGENT_DIR = ".config/opencode/agent"


def _render_claude(
    name: str,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> RenderedFile:
    """Render one Claude change agent as a home-relative ``RenderedFile`` record.

    Primary agents become the orchestrator skill; all others become subagents.
    """
    if _get_agent_mode(name, overrides=overrides, home=home) == "primary":
        rendered = _render_claude_skill(name, overrides=overrides)
        return RenderedFile(f"{_CLAUDE_SKILLS_DIR}/{name}/{rendered.filename}", rendered.content)
    rendered = _render_claude_agent(name, overrides=overrides)
    return RenderedFile(f"{_CLAUDE_AGENTS_DIR}/{rendered.filename}", rendered.content)


def _render_opencode(name: str, overrides: dict | None = None) -> RenderedFile:
    """Render one OpenCode change agent as a home-relative ``RenderedFile`` record."""
    rendered = _render_opencode_agent(name, overrides=overrides)
    return RenderedFile(f"{_OPENCODE_AGENT_DIR}/{rendered.filename}", rendered.content)


def _render_copilot_agent(name: str, overrides: dict | None = None) -> RenderedFile:
    """Render a change agent template into a Copilot agent file.

    Returns a :class:`RenderedFile` whose ``filename`` is ``<name>.agent.md``
    and whose ``content`` is the full rendered frontmatter + body.

    Frontmatter carries only ``name`` and ``description`` — no ``model``, ``tools``,
    ``user-invocable``, or ``disable-model-invocation``. The Copilot CLI ignores
    the agent ``model`` field (github/copilot-cli#1354, #2758) and its frontmatter
    support lags VS Code, so emitting more would write fields the CLI does not honor.
    This renderer intentionally does not read or require a copilot model entry in
    ``_AGENT_META`` (unlike the opencode/claude renderers).
    """
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
    """Render one Copilot change agent as a home-relative ``RenderedFile`` record."""
    rendered = _render_copilot_agent(name, overrides=overrides)
    return RenderedFile(f"{_COPILOT_AGENT_DIR}/{rendered.filename}", rendered.content)


# ---------------------------------------------------------------------------
# JSON metadata loader — task 4.
#
# Resource discovery and metadata decoding live behind the administrators
# and the public :func:`discover_agent_names`. The decoders translate
# ``agent-metadata/<name>.json`` into typed ``AgentMetadata`` /
# ``AgentCaps`` values; the schema validator rejects drift loudly so
# provider rendering can assume well-formed input.
# ---------------------------------------------------------------------------

#: Allowed top-level keys in an agent-metadata JSON resource. Unknown keys
#: fail loudly with :class:`ValueError` during decoding.
_METADATA_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"description", "mode", "model", "effort", "caps", "permission", "color"}
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
    unknown = set(raw) - _METADATA_ALLOWED_KEYS
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
    documented "drop the field" sentinel that admin renderers translate
    into "omit the provider frontmatter key". Other types fail loudly.
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


# ---------------------------------------------------------------------------
# Provider rendering helpers — translate AgentMetadata into provider-shaped
# frontmatter, body, and install-path artifacts.
#
# These functions are private (the public surface is the administrator
# classes); tests should assert behavior through the administrator's
# ``render_artifacts`` output. Translating to Artifact values keeps the
# install-path and content ownership inside each provider administrator.
# ---------------------------------------------------------------------------


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
    from ai_harness.modules.harness.override_store import deep_merge, load_override_store

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


def _claude_frontmatter(meta: AgentMetadata) -> str:
    """Render Claude subagent frontmatter from *meta*.

    Ordered keys: ``name``, ``description``, ``model``, optional ``effort``,
    optional ``tools``. ``effort`` is omitted when ``meta.effort.get("claude")``
    is ``None`` or absent. ``tools`` is omitted when ``meta.caps`` is the
    default :class:`AgentCaps` (full capability) — Claude's tools allow-list
    is a closed allowlist, so an unrestricted agent renders without it.
    """
    fm: dict[str, object] = {
        "name": meta.description,  # placeholder; replaced by caller with real name
    }
    # The caller is expected to populate the ``name`` key with the agent
    # identifier after this helper returns. Build the rest from *meta*.
    fm.pop("name")  # remove the placeholder
    fm["name"] = ""  # caller will overwrite with the agent name
    fm["description"] = meta.description
    model_claude = meta.model.get("claude")
    if model_claude is None:
        # Surface a clear error naming the agent — caller passes the name
        # through the exception to make it debuggable.
        raise ValueError(f"missing or invalid model.claude for {getattr(meta, 'description', '<unknown>')}")
    fm["model"] = model_claude

    # effort.claude = null → drop the field; absent → drop; string → emit.
    if "claude" in meta.effort and meta.effort["claude"] is not None:
        fm["effort"] = meta.effort["claude"]

    # caps != AgentCaps() → render a Claude tools allow-list.
    if meta.caps != AgentCaps():
        fm["tools"] = ", ".join(_claude_tools(meta.caps))

    return _yaml_dump_frontmatter(fm)


def _render_claude_agent_artifact(name: str, meta: AgentMetadata) -> Artifact:
    """Render a Claude subagent as an Artifact at ``.claude/agents/<name>.md``."""
    body = _read_template_body(name)
    fm: dict[str, object] = {
        "name": name,
        "description": meta.description,
        "model": meta.model.get("claude"),
    }
    # ``model.claude`` is required for Claude rendering.
    if not isinstance(fm["model"], str):
        raise ValueError(f"Template {name}: missing or invalid model.claude")
    if "claude" in meta.effort and meta.effort["claude"] is not None:
        fm["effort"] = meta.effort["claude"]
    if meta.caps != AgentCaps():
        fm["tools"] = ", ".join(_claude_tools(meta.caps))
    yaml_text = _yaml_dump_frontmatter(fm)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return Artifact(install_path=f"{_CLAUDE_AGENTS_DIR}/{name}.md", content=rendered)


def _render_claude_skill_artifact(name: str, meta: AgentMetadata) -> Artifact:
    """Render a primary Claude change agent as a skill Artifact.

    Skills carry only ``description`` in frontmatter — no model, effort,
    or tools. Overrides are intentionally ignored for skills: they run
    on the session model and inherit the user's effort setting. If
    ``caps.spawn`` is non-empty, append a spawn allowlist prose section
    because Claude skill frontmatter cannot enforce spawn restrictions.
    """
    if meta.mode != "primary":
        raise ValueError(f"Template {name}: mode must be primary for a skill, got {meta.mode!r}")
    if not isinstance(meta.model.get("claude"), str):
        raise ValueError(f"Template {name}: missing or invalid model.claude")
    body = _read_template_body(name)
    fm: dict[str, object] = {"description": meta.description}
    spawn_note = ""
    if meta.caps.spawn:
        names = ", ".join(f"`{a}`" for a in meta.caps.spawn)
        spawn_note = (
            "\n\n## Subagent spawn allowlist\n\n"
            "Claude skills cannot enforce spawn restrictions in frontmatter. "
            "The following prose constraint replaces the OpenCode "
            f"``permission.task`` allowlist:\n\n"
            f"Only spawn these subagents: {names}.\n"
        )
    yaml_text = _yaml_dump_frontmatter(fm)
    rendered = f"---\n{yaml_text}\n---\n{body}{spawn_note}"
    return Artifact(install_path=f"{_CLAUDE_SKILLS_DIR}/{name}/SKILL.md", content=rendered)


def _render_opencode_agent_artifact(name: str, meta: AgentMetadata) -> Artifact:
    """Render an OpenCode change agent as an Artifact at ``.config/opencode/agent/<name>.md``.

    Frontmatter keys (ordered): ``description``, ``mode``, ``model``,
    optional ``reasoningEffort``, optional ``permission``, optional ``color``.

    ``model.opencode`` is required; missing/non-string raises
    :class:`ValueError`. ``effort.opencode = null`` (or missing) omits
    the ``reasoningEffort`` key — the wizard clears effort for
    non-reasoning models and a stale ``reasoningEffort: null`` would
    violate the renderer contract.

    Explicit ``permission`` (raw dict) wins over caps-derived permission.
    Caps-derived permission is omitted when empty (no ``{}`` block on
    disk). ``color`` passes through when present; OpenCode accepts hex
    colors of the form ``#RGB``/``#RRGGBB`` or named colors (validation
    is left to OpenCode itself).
    """
    body = _read_template_body(name)
    model_opencode = meta.model.get("opencode")
    if not isinstance(model_opencode, str):
        raise ValueError(f"Template {name}: missing or invalid model.opencode")

    fm: dict[str, object] = {
        "description": meta.description,
        "mode": meta.mode,
        "model": model_opencode,
    }

    if "opencode" in meta.effort and meta.effort["opencode"] is not None:
        fm["reasoningEffort"] = meta.effort["opencode"]

    if meta.permission is not None:
        fm["permission"] = dict(meta.permission)
    else:
        derived = _opencode_permission(meta.caps)
        if derived:
            fm["permission"] = derived

    if isinstance(meta.color, str):
        fm["color"] = meta.color

    yaml_text = _yaml_dump_frontmatter(fm)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return Artifact(install_path=f"{_OPENCODE_AGENT_DIR}/{name}.md", content=rendered)
