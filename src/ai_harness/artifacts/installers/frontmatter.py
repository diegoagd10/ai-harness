"""Shared YAML-frontmatter serializer for composed agent artifacts.

A single deep, narrow helper that hides the frontmatter YAML layout behind
one call.  Both the Claude and Copilot installers (and the e2e suite) import
it so the composed-artifact format has exactly one source of truth.

The ``model:`` line is emitted ONLY when the metadata dict carries a
``"model"`` key.  Claude metadata always has it; Copilot metadata never does —
so "emit when present" unifies the two providers without a caller-side flag.
"""

from __future__ import annotations


def metadata_to_frontmatter(m: dict[str, object]) -> str:
    """Serialize a metadata dict to YAML frontmatter text.

    Produces lines like::

        ---
        name: jd-judge-a
        description: ...
        tools: [Read, Bash]
        model: opus   # only when "model" is present in *m*
        ---

    *tools* is a list of tool names (rendered as a flow sequence).
    """
    tools_yaml = ", ".join(str(t) for t in m["tools"])

    lines = [
        "---",
        f"name: {m['name']}",
        f"description: {m['description']}",
        f"tools: [{tools_yaml}]",
    ]
    if "model" in m:
        lines.append(f"model: {m['model']}")
    lines.append("---")
    return "\n".join(lines)


def copilot_frontmatter(m: dict[str, object]) -> str:
    """Serialize a metadata dict to Copilot custom-agent YAML frontmatter.

    Emits 7 unconditional keys in fixed order: name, description, tools,
    target, user-invocable, disable-model-invocation, model.

    Conditionally emits an 8th key ``agents:`` ONLY when ``m["agents"]`` is
    truthy.  ``target`` and ``disable-model-invocation`` are constants
    absorbed by the serializer — callers never pass them.

    Copilot docs (``agents`` field):
    https://code.visualstudio.com/docs/copilot/customization/custom-agents
    """
    tools_yaml = ", ".join(str(t) for t in m["tools"])

    lines = [
        "---",
        f"name: {m['name']}",
        f"description: {m['description']}",
        f"tools: [{tools_yaml}]",
        "target: github-copilot",
        f"user-invocable: {'true' if m.get('user-invocable') else 'false'}",
        "disable-model-invocation: true",
    ]
    if "model" in m:
        lines.append(f"model: {m['model']}")
    if m.get("agents"):
        lines.append("agents: [" + ", ".join(map(str, m["agents"])) + "]")
    lines.append("---")
    return "\n".join(lines)
