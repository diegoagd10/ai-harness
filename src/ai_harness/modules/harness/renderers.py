"""Per-provider agent renderers — transform a CLI-neutral agent template into a native agent file.

Each render function takes a template name and returns the rendered string with
CLI-specific frontmatter injected from code constants. Resource template files
contain only the shared prompt body — all metadata (description, mode, model,
permissions) lives in ``_AGENT_META`` below.

Public surface
--------------
render_agents           Render loop agents for a CLI as home-relative (path, content) pairs.
get_agent_meta          Return the metadata dict for a named agent.

All other render mechanics (per-CLI render functions, discovery, mode dispatch,
destination layout) are private and owned by ``render_agents``.
"""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path

import yaml

from ai_harness.modules.harness.models import AgentCli

_LOOP_AGENT_PACKAGE = "ai_harness.resources"
_LOOP_AGENT_DIR = "loop-agent"

# ---------------------------------------------------------------------------
# Agent metadata — single source of truth for description, mode, per-CLI
# models, and permission blocks. Resource templates carry only the prompt
# body; this constant is what the render functions read.
# ---------------------------------------------------------------------------

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
        "permission": {"edit": "deny", "write": "deny"},
    },
    "implementor": {
        "description": (
            "Implements one GitHub issue on an assigned branch. TDD, quality gates, "
            "ONE conventional commit with `Closes #N` in the body. Never closes the "
            "issue itself — the orchestrator closes it right after a clean validator "
            "pass. Reports BLOCKED if the issue cannot be resolved."
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
            "opencode": "openai/gpt-4.1-mini",
            "claude": "sonnet",
        },
        "permission": {"edit": "deny", "write": "deny"},
    },
    "loop-orchestrator": {
        "description": (
            "Loop orchestrator — drains loop-labeled sub-issues onto one per-session "
            "loop branch via explorer → implementor → validator subagents, looping "
            "implementor↔validator on any finding until clean, then opens ONE PR for "
            "the whole session. Never touches local main directly; closes each issue itself "
            "right after its validator pass is clean."
        ),
        "mode": "primary",
        "color": "error",
        "model": {
            "opencode": "openai/gpt-5.5",
            "claude": "sonnet",
        },
        "permission": {
            "task": {
                "*": "deny",
                "explorer": "allow",
                "implementor": "allow",
                "validator": "allow",
            },
            "edit": "deny",
            "write": "deny",
            "bash": "allow",
        },
    },
}


def _loop_agent_dir() -> Traversable:
    """Return the loop-agent resource directory path."""
    return files(_LOOP_AGENT_PACKAGE) / _LOOP_AGENT_DIR


# ---------------------------------------------------------------------------
# Override store — ``<home>/.ai-harness/overrides.json``
# ---------------------------------------------------------------------------

_OVERRIDES_REL = ".ai-harness/overrides.json"


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
    merged = _deep_merge_override_store(existing, payload)
    path = home / _OVERRIDES_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _deep_merge_override_store(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*, returning a fresh dict.

    Same shape as ``_deep_merge`` (used at render time) but operates on
    a fresh copy of *base* rather than the in-place render path so the
    wizard can keep its source-of-truth pristine between calls.
    """
    import copy

    result = copy.deepcopy(base)
    for key, value in override.items():
        base_value = result.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            result[key] = _deep_merge_override_store(base_value, value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _discover_loop_agents() -> list[str]:
    """Return sorted list of loop agent template names (without .md extension)."""
    root = _loop_agent_dir()
    names: list[str] = []
    for p in sorted(root.glob("*.md")):
        names.append(p.stem)
    return names


def _read_template_source(name: str) -> str:
    """Return the raw template text for a named agent (e.g. 'explorer')."""
    root = _loop_agent_dir()
    path = root / f"{name}.md"
    return path.read_text(encoding="utf-8")


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


def _read_template_body(name: str) -> str:
    """Return the prompt body for a named agent (full template text — no frontmatter)."""
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


def _render_opencode_agent(name: str, overrides: dict | None = None) -> tuple[str, str]:
    """Render a loop agent template into an OpenCode agent file.

    Returns (filename, content) where filename is ``<name>.md`` and content is
    the full rendered frontmatter + body.

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

    # Emit effort as OpenCode's ``reasoningEffort`` only when configured for this CLI
    effort_map = meta.get("effort")
    if isinstance(effort_map, dict) and "opencode" in effort_map:
        opencode_frontmatter["reasoningEffort"] = effort_map["opencode"]

    # Pass through the permission block if present
    if "permission" in meta:
        opencode_frontmatter["permission"] = meta["permission"]

    # Pass through color if present — OpenCode accepts a hex value or one of
    # primary, secondary, accent, success, warning, error, info.
    if "color" in meta:
        opencode_frontmatter["color"] = meta["color"]

    yaml_text = _yaml_dump_frontmatter(opencode_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return f"{name}.md", rendered


def _render_claude_agent(name: str, overrides: dict | None = None) -> tuple[str, str]:
    """Render a loop agent template into a Claude Code agent file.

    Returns (filename, content) where filename is ``<name>.md`` and content is
    the full rendered frontmatter + body.

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

    # Emit effort as Claude's ``effort`` only when configured for this CLI
    effort_map = meta.get("effort")
    if isinstance(effort_map, dict) and "claude" in effort_map:
        claude_frontmatter["effort"] = effort_map["claude"]

    # Translate OpenCode permission block to Claude-native tools allow-list
    permission = meta.get("permission")
    if isinstance(permission, dict) and permission.get("edit") == "deny" and permission.get("write") == "deny":
        tools = ["Read", "Grep", "Glob", "Bash"]
        if permission.get("bash") == "deny":
            tools.remove("Bash")
        claude_frontmatter["tools"] = ", ".join(tools)

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return f"{name}.md", rendered


def _render_claude_skill(name: str, overrides: dict | None = None) -> tuple[str, str]:
    """Render the primary loop agent template into a Claude Code skill file.

    Returns (filename, content) where filename is ``SKILL.md`` and content is
    the full rendered frontmatter + body.

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
    permission = meta.get("permission")
    if isinstance(permission, dict) and "task" in permission:
        task_perms = permission["task"]
        allowed = [agent for agent, access in task_perms.items() if access == "allow" and agent != "*"]
        if allowed:
            names = ", ".join(f"`{a}`" for a in allowed)
            spawn_note = (
                "\n\n## Subagent spawn allowlist\n\n"
                "Claude skills cannot enforce spawn restrictions in frontmatter. "
                "The following prose constraint replaces the OpenCode "
                f"``permission.task`` allowlist:\n\n"
                f"Only spawn these subagents: {names}.\n"
            )

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}{spawn_note}"
    return "SKILL.md", rendered


# ---------------------------------------------------------------------------
# Agent-render seam — the sole public entry for rendered-agent emission.
# Owns skill-vs-agent mode dispatch, destination directory layout, and
# filename. Callers state the CLI; they never assemble paths themselves.
# ---------------------------------------------------------------------------

_CLAUDE_AGENTS_DIR = ".claude/agents"
_CLAUDE_SKILL_DIR = ".claude/skills/loop-orchestrator"
_OPENCODE_AGENT_DIR = ".config/opencode/agent"


def _render_claude(
    name: str,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> tuple[str, str]:
    """Render one Claude loop agent as a home-relative (path, content) pair.

    Primary agents become the orchestrator skill; all others become subagents.
    """
    if _get_agent_mode(name, overrides=overrides, home=home) == "primary":
        filename, content = _render_claude_skill(name, overrides=overrides)
        return f"{_CLAUDE_SKILL_DIR}/{filename}", content
    filename, content = _render_claude_agent(name, overrides=overrides)
    return f"{_CLAUDE_AGENTS_DIR}/{filename}", content


def _render_opencode(name: str, overrides: dict | None = None) -> tuple[str, str]:
    """Render one OpenCode loop agent as a home-relative (path, content) pair."""
    filename, content = _render_opencode_agent(name, overrides=overrides)
    return f"{_OPENCODE_AGENT_DIR}/{filename}", content


def render_agents(
    cli: AgentCli,
    names: list[str] | None = None,
    overrides: dict | None = None,
    *,
    home: Path | None = None,
) -> list[tuple[str, str]]:
    """Render the loop agents for *cli* as home-relative (path, content) pairs.

    The sole public agent-render entry. Owns skill-vs-agent mode dispatch,
    destination directory layout, and filename. Returns POSIX home-relative
    paths in discovery (sorted) order so output is byte-identical to the prior
    inline emission.

    *names* defaults to the discovered loop agents; pass an explicit list to
    render a subset. *overrides* is an optional per-agent partial overlay
    deep-merged over the template defaults; ``None`` loads the override
    store from ``home/.ai-harness/overrides.json`` (default
    ``Path.home()``), ``{}`` is an explicit no-op. CLIs without native
    agent support return an empty list.
    """
    if names is None:
        names = _discover_loop_agents()

    if overrides is None:
        overrides = _load_override_store(home if home is not None else Path.home())

    if cli == AgentCli.CLAUDE:
        return [_render_claude(name, overrides=overrides) for name in names]
    if cli == AgentCli.OPENCODE:
        return [_render_opencode(name, overrides=overrides) for name in names]
    return []
