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
    """Serialize a ``_METADATA`` entry to YAML frontmatter text.

    Produces lines like::

        ---
        name: jd-judge-a
        description: ...
        tools: [Read, Bash]
        model: opus   # only when "model" is present in *m*
        ---

    *tools* may be a list (rendered as a flow sequence) or a scalar.
    """
    tools = m["tools"]
    if isinstance(tools, list):
        tools_yaml = ", ".join(str(t) for t in tools)
    else:
        tools_yaml = str(tools)

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
