"""Per-provider agent renderers — transform a CLI-neutral agent template into a native agent file.

Each render function takes a template name and returns the rendered string with
CLI-specific frontmatter injected from code constants. Resource template files
contain only the shared prompt body — all metadata (description, mode, model,
permissions) lives in ``_AGENT_META`` below.

Public surface
--------------
render_opencode_agent   Turn an agent template into an OpenCode agent file.
render_claude_agent     Turn a subagent template into a Claude Code agent file.
render_claude_skill     Turn the primary template into a Claude Code skill file.
_discover_loop_agents   Return sorted list of loop agent template names.
_read_template_source   Return the raw template text for a named agent.
_read_template_body     Return the prompt body for a named agent.
get_agent_meta          Return the metadata dict for a named agent.
_get_agent_mode         Return the mode (subagent|primary) for a named agent.
"""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable

import yaml

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
            "Loop orchestrator — drains ready-for-agent GitHub issues onto one per-session "
            "loop branch via explorer → implementor → validator subagents, looping "
            "implementor↔validator on any finding until clean, then opens ONE PR for "
            "the whole session. Never touches local main directly; closes each issue itself "
            "right after its validator pass is clean."
        ),
        "mode": "primary",
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


def get_agent_meta(name: str) -> dict:
    """Return the metadata dict for a named agent (from ``_AGENT_META``).

    Public so tests can derive expected frontmatter from the same source.
    """
    meta = _AGENT_META.get(name)
    if meta is None:
        raise ValueError(f"Unknown agent template: {name!r}")
    return meta


def _get_agent_mode(name: str) -> str:
    """Return the mode (subagent|primary) for a named agent."""
    return get_agent_meta(name).get("mode", "subagent")


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


def render_opencode_agent(name: str) -> tuple[str, str]:
    """Render a loop agent template into an OpenCode agent file.

    Returns (filename, content) where filename is ``<name>.md`` and content is
    the full rendered frontmatter + body.

    Raises ValueError if the agent's metadata lacks ``model.opencode``.
    """
    meta = get_agent_meta(name)
    body = _read_template_body(name)

    model_map = meta.get("model")
    if not isinstance(model_map, dict) or "opencode" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.opencode")

    opencode_frontmatter: dict[str, object] = {
        "description": meta.get("description", ""),
        "mode": meta.get("mode", "subagent"),
        "model": model_map["opencode"],
    }

    # Pass through the permission block if present
    if "permission" in meta:
        opencode_frontmatter["permission"] = meta["permission"]

    yaml_text = _yaml_dump_frontmatter(opencode_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return f"{name}.md", rendered


def render_claude_agent(name: str) -> tuple[str, str]:
    """Render a loop agent template into a Claude Code agent file.

    Returns (filename, content) where filename is ``<name>.md`` and content is
    the full rendered frontmatter + body.

    Raises ValueError if the agent lacks ``model.claude`` or has ``mode: primary``.
    """
    meta = get_agent_meta(name)
    body = _read_template_body(name)

    model_map = meta.get("model")
    if not isinstance(model_map, dict) or "claude" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.claude")

    mode = meta.get("mode", "subagent")
    if mode == "primary":
        raise ValueError(f"Template {name}: mode=primary — use render_claude_skill for the primary agent")

    claude_frontmatter: dict[str, object] = {
        "description": meta.get("description", ""),
        "mode": mode,
        "model": model_map["claude"],
    }

    # Read-only narrowing: if permission denies edit AND write, emit tools allow-list
    permission = meta.get("permission")
    if isinstance(permission, dict) and permission.get("edit") == "deny" and permission.get("write") == "deny":
        claude_frontmatter["tools"] = "Read, Grep, Glob, Bash"

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return f"{name}.md", rendered


def render_claude_skill(name: str) -> tuple[str, str]:
    """Render the primary loop agent template into a Claude Code skill file.

    Returns (filename, content) where filename is ``SKILL.md`` and content is
    the full rendered frontmatter + body.

    Raises ValueError if the agent lacks ``model.claude`` or has mode other than ``primary``.
    """
    meta = get_agent_meta(name)
    body = _read_template_body(name)

    model_map = meta.get("model")
    if not isinstance(model_map, dict) or "claude" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.claude")

    mode = meta.get("mode", "subagent")
    if mode != "primary":
        raise ValueError(f"Template {name}: mode must be primary for a skill, got {mode!r}")

    claude_frontmatter: dict[str, object] = {
        "description": meta.get("description", ""),
        "mode": mode,
    }
    # No model field — skills run on the session model.
    # No tools field — unrestricted.

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---\n{body}"
    return "SKILL.md", rendered
