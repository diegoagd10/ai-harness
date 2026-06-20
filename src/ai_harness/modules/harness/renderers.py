"""Per-provider agent renderers — transform a CLI-neutral agent template into a native agent file.

Each render function takes a template path and returns the rendered string (or
raises ValueError if the template lacks required frontmatter for that provider).

Public surface
--------------
render_opencode_agent   Turn an agent template into an OpenCode agent file.
render_claude_agent     Turn a subagent template into a Claude Code agent file.
render_claude_skill     Turn the primary template into a Claude Code skill file.
_discover_loop_agents   Return sorted list of loop agent template names.
_read_template_source   Return the raw template text for a named agent.
"""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable

import yaml

_LOOP_AGENT_PACKAGE = "ai_harness.resources"
_LOOP_AGENT_DIR = "loop-agent"


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


def render_opencode_agent(name: str) -> tuple[str, str]:
    """Render a loop agent template into an OpenCode agent file.

    Returns (filename, content) where filename is ``<name>.md`` and content is
    the full rendered frontmatter + body.

    Raises ValueError if the template lacks ``model.opencode``.
    """
    frontmatter, body = _parse_template(name)

    model_map = frontmatter.get("model")
    if not isinstance(model_map, dict) or "opencode" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.opencode")

    opencode_frontmatter: dict[str, object] = {
        "description": frontmatter.get("description", ""),
        "mode": frontmatter.get("mode", "subagent"),
        "model": model_map["opencode"],
    }

    # Pass through the permission block if present
    if "permission" in frontmatter:
        opencode_frontmatter["permission"] = frontmatter["permission"]

    yaml_text = _yaml_dump_frontmatter(opencode_frontmatter)
    rendered = f"---\n{yaml_text}\n---{body}"
    return f"{name}.md", rendered


def _parse_template(name: str) -> tuple[dict, str]:
    """Parse shared template frontmatter and body, return (frontmatter_dict, body_string)."""
    source = _read_template_source(name)
    parts = source.split("---")
    if len(parts) < 3:
        raise ValueError(f"Template {name}: no frontmatter found (expected --- ... --- body)")

    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        raise ValueError(f"Template {name}: frontmatter is not a mapping")

    body = "---".join(parts[2:])
    return frontmatter, body


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


def render_claude_agent(name: str) -> tuple[str, str]:
    """Render a loop agent template into a Claude Code agent file.

    Returns (filename, content) where filename is ``<name>.md`` and content is
    the full rendered frontmatter + body.

    Raises ValueError if the template lacks ``model.claude`` or has ``mode: primary``.
    """
    frontmatter, body = _parse_template(name)

    model_map = frontmatter.get("model")
    if not isinstance(model_map, dict) or "claude" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.claude")

    mode = frontmatter.get("mode", "subagent")
    if mode == "primary":
        raise ValueError(f"Template {name}: mode=primary — use render_claude_skill for the primary agent")

    claude_frontmatter: dict[str, object] = {
        "description": frontmatter.get("description", ""),
        "mode": mode,
        "model": model_map["claude"],
    }

    # Read-only narrowing: if permission denies edit AND write, emit tools allow-list
    permission = frontmatter.get("permission")
    if isinstance(permission, dict) and permission.get("edit") == "deny" and permission.get("write") == "deny":
        claude_frontmatter["tools"] = "Read, Grep, Glob, Bash"

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---{body}"
    return f"{name}.md", rendered


def render_claude_skill(name: str) -> tuple[str, str]:
    """Render the primary loop agent template into a Claude Code skill file.

    Returns (filename, content) where filename is ``SKILL.md`` and content is
    the full rendered frontmatter + body.

    Raises ValueError if the template lacks ``model.claude`` or has mode other than ``primary``.
    """
    frontmatter, body = _parse_template(name)

    model_map = frontmatter.get("model")
    if not isinstance(model_map, dict) or "claude" not in model_map:
        raise ValueError(f"Template {name}: missing or invalid model.claude")

    mode = frontmatter.get("mode", "subagent")
    if mode != "primary":
        raise ValueError(f"Template {name}: mode must be primary for a skill, got {mode!r}")

    claude_frontmatter: dict[str, object] = {
        "description": frontmatter.get("description", ""),
        "mode": mode,
    }
    # No model field — skills run on the session model.
    # No tools field — unrestricted.

    yaml_text = _yaml_dump_frontmatter(claude_frontmatter)
    rendered = f"---\n{yaml_text}\n---{body}"
    return "SKILL.md", rendered
