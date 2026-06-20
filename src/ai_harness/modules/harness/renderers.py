"""Per-provider agent renderers — transform a CLI-neutral agent template into a native agent file.

Each render function takes a template path and returns the rendered string (or
raises ValueError if the template lacks required frontmatter for that provider).

Public surface
--------------
render_opencode_agent   Turn an agent template into an OpenCode agent file.
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
    source = _read_template_source(name)
    parts = source.split("---")
    if len(parts) < 3:
        raise ValueError(f"Template {name}: no frontmatter found (expected --- ... --- body)")

    frontmatter = yaml.safe_load(parts[1])
    if not isinstance(frontmatter, dict):
        raise ValueError(f"Template {name}: frontmatter is not a mapping")

    body = "---".join(parts[2:])

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

    # Deterministic YAML dump: sort keys, no anchors/aliases, consistent style
    yaml_text = yaml.dump(
        opencode_frontmatter,
        sort_keys=True,
        default_flow_style=False,
        explicit_start=False,
        explicit_end=False,
        allow_unicode=True,
    ).rstrip("\n")

    # Body already starts with its own leading newline from the template split
    rendered = f"---\n{yaml_text}\n---{body}"
    return f"{name}.md", rendered
