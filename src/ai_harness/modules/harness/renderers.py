"""Per-provider agent renderers — transform a CLI-neutral agent template into a native agent file.

Each render function takes a template name and returns the rendered string with
CLI-specific frontmatter injected from code constants. Resource template files
contain only the shared prompt body — all metadata (description, mode, model,
permissions) lives in ``_AGENT_META``.

Public surface
--------------
AgentCaps              What an agent may do, in CLI-neutral terms.
RenderedFile           One rendered agent file: a home-relative path and the file's full content.
render_agents          Render loop agents for a CLI as home-relative ``RenderedFile`` records.
get_agent_meta         Return the metadata dict for a named agent.
write_override_store   Deep-merge into the per-agent override store at ``~/.ai-harness/overrides.json``.

All other render mechanics (per-CLI render functions, discovery, mode dispatch,
destination layout) are private and owned by ``render_agents``.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import NamedTuple

import yaml

from ai_harness.modules.harness.models import AgentCli

__all__ = [
    "AgentCaps",
    "RenderedFile",
    "get_agent_meta",
    "render_agents",
    "write_override_store",
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOOP_AGENT_PACKAGE = "ai_harness.resources"
_LOOP_AGENT_DIR = "loop-agent"
_GENERIC_AGENT_DIR = "generic"
_SDD_AGENT_DIR = "sdd-agent"

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
# Public functions
# ---------------------------------------------------------------------------


def render_agents(
    cli: AgentCli,
    names: list[str] | None = None,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> list[RenderedFile]:
    """Render the loop and SDD agents for *cli* as home-relative ``RenderedFile`` records.

    The sole public agent-render entry. Owns skill-vs-agent mode dispatch,
    destination directory layout, and filename. Returns POSIX home-relative
    paths in discovery (sorted) order so output is byte-identical to the prior
    inline emission.

    *names* defaults to the discovered agents (Loop trio + ``loop-orchestrator``
    + SDD trio); pass an explicit list to render a subset. *overrides* is an
    optional per-agent partial overlay deep-merged over the template defaults;
    ``None`` loads the override store from ``home/.ai-harness/overrides.json``
    (default ``Path.home()``), ``{}`` is an explicit no-op. CLIs without
    native agent support return an empty list.
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
    "explorer": {
        "description": (
            "Read-only investigator. Given a GitHub issue, returns a focused plan "
            "(affected files, steps, edge cases, test surface, risks) before implementation begins."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "opencode-go/kimi-k2.7-code",
            "claude": "sonnet",
        },
        "caps": AgentCaps(write=False),
    },
    "implementor": {
        "description": (
            "Implements one GitHub issue on the worktree's current branch. TDD, quality gates, "
            "ONE commit whose format follows CODING_STANDARDS.md ## Commits; the "
            "issue number must appear in the commit. Never closes the issue itself "
            "— the orchestrator closes it right after a clean validator pass. "
            "Reports BLOCKED if the issue cannot be resolved."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "opencode-go/deepseek-v4-pro",
            "claude": "sonnet",
        },
    },
    "validator": {
        "description": (
            "Read-only reviewer. Audits the diff for correctness, edge cases, type safety, "
            "and quality-gate compliance. Verifies the implementation covers the user stories "
            "from the parent PRD. Emits BLOCKER | CRITICAL | WARNING | SUGGESTION findings."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "openai/gpt-5.4-mini",
            "claude": "sonnet",
        },
        "caps": AgentCaps(write=False),
    },
    "loop-orchestrator": {
        "description": (
            "Loop orchestrator — drains loop-labeled sub-issues onto the worktree's current "
            "branch via explorer → implementor → validator subagents, looping "
            "implementor↔validator on any finding until clean, then opens ONE PR for "
            "the whole session. Never creates branches or touches main directly; closes each "
            "issue itself right after its validator pass is clean."
        ),
        "mode": "primary",
        "color": "error",
        "model": {
            "opencode": "openai/gpt-5.5",
            "claude": "sonnet",
        },
        "caps": AgentCaps(write=False, spawn=("explorer", "implementor", "validator")),
    },
    "Sdd-Planning-Loop": {
        "description": (
            "SDD Planning Loop orchestrator — drives the file-backed planning flow for one named "
            "change. User runs /grill-with-docs or /grill-me to reach shared understanding, then "
            "the orchestrator delegates explore -> propose -> spec -> design -> tasks to fresh "
            "subagents, derived from which artifacts already exist in docs/changes/<name>/. "
            "Stops when all five artifacts are present (change is ready)."
        ),
        "mode": "primary",
        "color": "error",
        "model": {
            "opencode": "openai/gpt-5.5",
            "claude": "sonnet",
        },
        "caps": AgentCaps(write=False, spawn=("sdd-explorer", "sdd-propose", "sdd-spec", "sdd-design", "sdd-tasks")),
    },
    "Sdd-Implementor-Loop": {
        "description": (
            "SDD Implementation Loop orchestrator — drives the file-backed apply ↔ verify "
            "fix-up loop for one named change until the validator is clean, then archives "
            "and opens ONE PR. Runs inside the worktree; other ready changes are untouched."
        ),
        "mode": "primary",
        "color": "error",
        "model": {
            "opencode": "openai/gpt-5.5",
            "claude": "sonnet",
        },
        "caps": AgentCaps(write=False, spawn=("sdd-implementor", "sdd-validator", "sdd-archive")),
    },
    "sdd-explorer": {
        "description": (
            "Read-only investigator for the SDD change-flow. Reads the change folder "
            "and writes exploration.md into docs/changes/<name>/ before implementation."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "opencode-go/kimi-k2.7-code",
            "claude": "sonnet",
        },
        "caps": AgentCaps(write=False),
    },
    "sdd-implementor": {
        "description": (
            "Implements one named SDD change. TDD, quality gates, ONE commit "
            "referencing the change name (no #issue). Marks items [x] in tasks.md. "
            "No GitHub issue comment on blocked — the change is file-backed."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "opencode-go/deepseek-v4-pro",
            "claude": "sonnet",
        },
    },
    "sdd-validator": {
        "description": (
            "Read-only reviewer for the SDD change-flow. Emits verify-report.md containing "
            "a Spec Compliance Matrix: one row per Given/When/Then scenario mapped "
            "to a passing covering test. CRITICAL UNTESTED for any scenario with no "
            "passing test. Blocks the change from being archived while untested."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "openai/gpt-5.4-mini",
            "claude": "sonnet",
        },
        "caps": AgentCaps(write=False),
    },
    # SDD-only phase agents — single-file bodies under sdd-agent/, no
    # generic/loop-agent layer (passthrough composition). They move the
    # change artifact-by-artifact through propose -> spec -> design -> tasks,
    # then archive once the validator's report is clean. Tunable via
    # overrides.json like every other agent.
    "sdd-propose": {
        "description": (
            "Authors the proposal artifact of an SDD change — reads the change "
            "folder and writes proposal.md with Intent, In/Out of scope, "
            "Approach, and Risks. Bounds every later phase; touches no code."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "opencode-go/deepseek-v4-pro",
            "claude": "sonnet",
        },
    },
    "sdd-spec": {
        "description": (
            "Authors the standalone full specification of an SDD change. Writes "
            "spec.md as Requirements with RFC-2119 strength keywords and flat "
            "UPPERCASE GIVEN/WHEN/THEN/AND scenarios — at least one per "
            "requirement covering happy path, edge case, and error state; each "
            "scenario automatable. No delta sections, no central spec store."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "opencode-go/deepseek-v4-pro",
            "claude": "sonnet",
        },
    },
    "sdd-design": {
        "description": (
            "Authors the deep-module design of an SDD change. Reads spec.md and "
            "writes design.md naming the deep modules, their interfaces, and "
            "the seams where the new code plugs into the existing tree. Touches "
            "no code."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "opencode-go/deepseek-v4-pro",
            "claude": "sonnet",
        },
    },
    "sdd-tasks": {
        "description": (
            "Extracts the task list for an SDD change from spec.md and "
            "design.md. Writes tasks.md as a flat '- [ ]' checklist in TDD "
            "order (test first), one task doing one named thing; the last task "
            "is always all quality gates green."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "openai/gpt-5.4-mini",
            "claude": "sonnet",
        },
    },
    "sdd-archive": {
        "description": (
            "Archives a completed SDD change once verify-report.md's first line "
            "is exactly 'No findings.'. Moves docs/changes/<name>/ to "
            "docs/changes/archive/<YYYY-MM-DD>-<name>/ using today's ISO date. "
            "Blocks on any open finding."
        ),
        "mode": "subagent",
        "model": {
            "opencode": "openai/gpt-5.4-mini",
            "claude": "sonnet",
        },
    },
}


def _loop_agent_dir() -> Traversable:
    """Return the loop-agent resource directory path."""
    return files(_LOOP_AGENT_PACKAGE) / _LOOP_AGENT_DIR


def _generic_agent_dir() -> Traversable:
    """Return the generic agent resource directory path.

    Holds the shared-core layer of the three split loop agents
    (``explorer``/``implementor``/``validator``). Single-file agents that have
    no generic layer are returned unchanged by :func:`_read_template_body`.
    """
    return files(_LOOP_AGENT_PACKAGE) / _GENERIC_AGENT_DIR


def _sdd_agent_dir() -> Traversable:
    """Return the sdd-agent resource directory path.

    Holds the SDD-flow overlays (``sdd-explorer``/``sdd-implementor``/
    ``sdd-validator``) composed over the same generic core the Loop trio uses.
    The overlay is appended to ``generic/<base>.md`` where ``base`` is the
    SDD name with the ``sdd-`` prefix stripped (see :func:`_read_template_body`).
    """
    return files(_LOOP_AGENT_PACKAGE) / _SDD_AGENT_DIR


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
    """Return the sorted, deduped list of composed agent template names.

    Scans both ``loop-agent/`` and ``sdd-agent/`` and returns the union of
    their stems (without ``.md``), sorted alphabetically. The Loop trio and
    ``loop-orchestrator`` come from ``loop-agent/``; the SDD trio
    (``sdd-explorer``/``sdd-implementor``/``sdd-validator``) comes from
    ``sdd-agent/``. Single-file SDD planning agents (future) will also be
    discovered here once they land under ``sdd-agent/``.
    """
    loop_names = [p.stem for p in _loop_agent_dir().glob("*.md")]
    sdd_names = [p.stem for p in _sdd_agent_dir().glob("*.md")]
    return sorted(set(loop_names) | set(sdd_names))


def _read_template_source(name: str) -> str:
    """Return the raw template text for a named agent (e.g. 'explorer').

    Lookups up the ``loop-agent/`` resource first (Loop trio + loop-orchestrator
    + split-agent overlays), then fall back to ``sdd-agent/``. The fallback
    covers the SDD-only phase agents (``sdd-propose`` / ``sdd-spec`` /
    ``sdd-design`` / ``sdd-tasks`` / ``sdd-archive``), which are single-file
    bodies with no generic layer — :func:`_read_template_body` returns them
    unchanged via this helper. Raises ``FileNotFoundError`` when no template
    exists under either resource directory.
    """
    loop_path = _loop_agent_dir() / f"{name}.md"
    if loop_path.is_file():
        return loop_path.read_text(encoding="utf-8")
    sdd_path = _sdd_agent_dir() / f"{name}.md"
    if sdd_path.is_file():
        return sdd_path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"No template found for {name!r} in loop-agent or sdd-agent")


def _read_template_body(name: str) -> str:
    """Return the prompt body for a named agent.

    Composed from ``generic/<name>.md`` + ``<flow>-agent/<name>.md`` by plain
    concatenation. The Loop flow composes ``loop-agent/<name>`` over
    ``generic/<name>``; the SDD flow strips the ``sdd-`` prefix to reuse the
    same generic core and composes ``sdd-agent/<name>`` over it. Single-file
    agents (no generic layer — e.g. ``loop-orchestrator``) are returned
    unchanged from the ``loop-agent/`` resource.

    The Loop trio's composed body is byte-identical to the pre-split single
    file (regression-guarded by ``TestCompositionGoldenFixture``); the SDD
    trio's composed body is ``generic/<base>`` + the SDD overlay, where
    ``<base>`` is ``<name>`` with the ``sdd-`` prefix removed.
    """
    generic_path = _generic_agent_dir() / f"{name}.md"
    if generic_path.is_file():
        overlay_path = _loop_agent_dir() / f"{name}.md"
        return generic_path.read_text(encoding="utf-8") + overlay_path.read_text(encoding="utf-8")

    # SDD variant: strip the "sdd-" prefix to find the shared generic core,
    # then compose the SDD overlay over it. The generic core is the same one
    # the Loop trio uses; the SDD overlay appends change-flow-specific
    # sections that supersede the generic's issue-shaped ones in prose.
    if name.startswith("sdd-"):
        base = name[len("sdd-") :]
        generic_base = _generic_agent_dir() / f"{base}.md"
        if generic_base.is_file():
            overlay_path = _sdd_agent_dir() / f"{name}.md"
            return generic_base.read_text(encoding="utf-8") + overlay_path.read_text(encoding="utf-8")

    # Single-file agent (e.g. loop-orchestrator) — no generic layer, no SDD
    # variant. Read directly from the loop-agent resource.
    return _read_template_source(name)


def _yaml_dump_frontmatter(data: dict[str, object]) -> str:
    """Deterministic YAML dump for frontmatter blocks."""
    return yaml.dump(
        data,
        sort_keys=True,
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
    """Render a loop agent template into an OpenCode agent file.

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
    caps = meta.get("caps")
    if isinstance(caps, AgentCaps):
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
    """Render a loop agent template into a Claude Code agent file.

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
    """Render the primary loop agent template into a Claude Code skill file.

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
_COPILOT_AGENT_DIR = ".copilot/agents"
_OPENCODE_AGENT_DIR = ".config/opencode/agent"


def _claude_skill_dir(name: str) -> str:
    """Return the Claude skill directory for a ``mode: primary`` agent name.

    Each primary agent renders into its own skill directory derived from its
    name, so a new primary (e.g. ``Sdd-Planning-Loop``) lands in
    ``.claude/skills/Sdd-Planning-Loop/`` without disturbing another primary's
    directory. For ``loop-orchestrator`` this returns the prior hardcoded
    constant ``.claude/skills/loop-orchestrator`` byte-for-byte.
    """
    return f".claude/skills/{name}"


def _render_claude(
    name: str,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> RenderedFile:
    """Render one Claude loop agent as a home-relative ``RenderedFile`` record.

    Primary agents become the orchestrator skill in their own per-primary dir;
    all others become subagents.
    """
    if _get_agent_mode(name, overrides=overrides, home=home) == "primary":
        rendered = _render_claude_skill(name, overrides=overrides)
        return RenderedFile(f"{_claude_skill_dir(name)}/{rendered.filename}", rendered.content)
    rendered = _render_claude_agent(name, overrides=overrides)
    return RenderedFile(f"{_CLAUDE_AGENTS_DIR}/{rendered.filename}", rendered.content)


def _render_opencode(name: str, overrides: dict | None = None) -> RenderedFile:
    """Render one OpenCode loop agent as a home-relative ``RenderedFile`` record."""
    rendered = _render_opencode_agent(name, overrides=overrides)
    return RenderedFile(f"{_OPENCODE_AGENT_DIR}/{rendered.filename}", rendered.content)


def _render_copilot_agent(name: str, overrides: dict | None = None) -> RenderedFile:
    """Render a loop agent template into a Copilot agent file.

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
    """Render one Copilot loop agent as a home-relative ``RenderedFile`` record."""
    rendered = _render_copilot_agent(name, overrides=overrides)
    return RenderedFile(f"{_COPILOT_AGENT_DIR}/{rendered.filename}", rendered.content)
