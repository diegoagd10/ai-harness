"""Generators: render the OpenCode-specific artifacts at install time.

Two outputs come from this module:

- ``opencode.json``: the per-host agent config; written verbatim from the
  canonical source with ``{{HOME}}`` substituted to the real home path.
- slash-command files: per-canonical-source ``*.md`` rendered with the
  OpenCode frontmatter dialect and four body placeholders substituted.

Both are host-injectable: the caller supplies every directory and the
``home`` value, so the generators stay testable against temp dirs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Action vocabulary for the generator report. Mirrors the Go ``commands`` and
# ``opencode`` packages so the CLI can print a unified report.
ACTION_GENERATED = "generated"
ACTION_REMOVED = "removed"
ACTION_ABSENT = "absent"

# Canonical source layout (relative to repo root).
COMMANDS_SUBDIR = Path("prompts") / "commands"
OPENCODE_SOURCE = Path("agent-clis") / "opencode" / "opencode.json"
OPENCODE_DEST_NAME = "opencode.json"

# Canonical frontmatter fence and placeholder tokens.
FRONTMATTER_FENCE = "---"
ORCHESTRATOR_AGENT_TOKEN = "{{ORCHESTRATOR_AGENT}}"
SKILLS_DIR_TOKEN = "{{SKILLS_DIR}}"
CWD_NOTE_TOKEN = "{{CWD_NOTE}}"
ARGS_TOKEN = "{{ARGS}}"
HOME_TOKEN = "{{HOME}}"

# OpenCode-specific defaults for the slash-command substitution. Mirrors the
# Go ``opencodeCwdNote`` literal; the leading space keeps the body template
# tidy when the note is empty (so "workspace.{{CWD_NOTE}}" does not dangle).
OPENCODE_CWD_NOTE = (
    " In OpenCode Desktop (Electron) the parse-time interpolation resolves "
    "to the app data directory, not the project."
)


@dataclass(frozen=True)
class GenerateOutcome:
    """Per-file generator result.

    ``dest`` is the file the generator wrote (or tried to remove),
    ``src`` is the canonical source it was rendered from (Generate only;
    empty for remove outcomes), and ``action`` is the verb the CLI prints.
    """

    dest: Path
    src: Path | None
    action: str


def substitute(
    body: str,
    *,
    orchestrator_agent: str,
    skills_dir: str,
    cwd_note: str,
    args_token: str,
) -> str:
    """Replace the four canonical placeholders in ``body``.

    Plain string replacement: the placeholder set is fixed and tiny, so a
    template engine would be overkill. Unknown placeholders stay raw so
    the user notices typos instead of silently getting a partial render.
    """
    return (
        body.replace(ORCHESTRATOR_AGENT_TOKEN, orchestrator_agent)
        .replace(SKILLS_DIR_TOKEN, skills_dir)
        .replace(CWD_NOTE_TOKEN, cwd_note)
        .replace(ARGS_TOKEN, args_token)
    )


def render_opencode_frontmatter(description: str, agent: str, *, subtask: bool) -> str:
    """Emit the OpenCode frontmatter block (description, agent, subtask).

    OpenCode has no ``read-only`` field, so the neutral ``readOnly`` flag
    from the canonical source is intentionally dropped here. ``subtask``
    is omitted when false to keep the rendered file compact.
    """
    lines = [FRONTMATTER_FENCE, f"description: {description}", f"agent: {agent}"]
    if subtask:
        lines.append("subtask: true")
    lines.append(FRONTMATTER_FENCE)
    return "\n".join(lines) + "\n"


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Separate the leading ``---``-fenced block from the body.

    The canonical files use a flat ``key: value`` form, so a full YAML
    parser would be overkill. Returns (header, body); raises
    :class:`ValueError` when either fence is missing.
    """
    if not text.startswith(FRONTMATTER_FENCE + "\n"):
        raise ValueError("missing leading frontmatter fence")
    rest = text[len(FRONTMATTER_FENCE) + 1 :]
    end = rest.find("\n" + FRONTMATTER_FENCE + "\n")
    if end < 0:
        raise ValueError("missing closing frontmatter fence")
    header = rest[:end]
    body = rest[end + len("\n" + FRONTMATTER_FENCE + "\n") :]
    return header, body


def _parse_frontmatter(header: str) -> dict[str, str]:
    """Parse a flat ``key: value`` frontmatter header.

    Unknown keys are ignored so the canonical source can grow new keys
    without breaking older installers. The OpenCode dialect today only
    reads ``description`` and ``subtask``.
    """
    parsed: dict[str, str] = {}
    for line in header.split("\n"):
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        parsed[key.strip()] = value.strip()
    return parsed


# --- opencode.json ---------------------------------------------------------


def generate_opencode_json(repo_dir: Path, opencode_dir: Path, home: str) -> GenerateOutcome:
    """Substitute ``{{HOME}}`` and write ``opencode.json`` to ``opencode_dir``.

    A missing source is an error: callers should know the canonical source
    is broken rather than silently shipping a partial install.

    The write is rollback-safe: if ``write_text`` fails after partially
    mutating the file, the original content is restored (or the file is
    removed when it was newly created).
    """
    src = repo_dir / OPENCODE_SOURCE
    dest = opencode_dir / OPENCODE_DEST_NAME
    raw = src.read_text(encoding="utf-8")
    rendered = raw.replace(HOME_TOKEN, home)
    opencode_dir.mkdir(parents=True, exist_ok=True)
    # Snapshot pre-existing content so a partial write failure can restore it.
    previous: bytes | None = None
    if dest.exists():
        previous = dest.read_bytes()
    try:
        dest.write_text(rendered, encoding="utf-8")
    except Exception:
        try:
            if previous is None:
                dest.unlink(missing_ok=True)
            else:
                dest.write_bytes(previous)
        except OSError:
            pass
        raise
    return GenerateOutcome(dest=dest, src=src, action=ACTION_GENERATED)


def remove_opencode_json(opencode_dir: Path) -> GenerateOutcome:
    """Delete ``opencode.json`` if present, else report ``absent``."""
    dest = opencode_dir / OPENCODE_DEST_NAME
    try:
        dest.unlink()
        return GenerateOutcome(dest=dest, src=None, action=ACTION_REMOVED)
    except FileNotFoundError:
        return GenerateOutcome(dest=dest, src=None, action=ACTION_ABSENT)


# --- slash commands -------------------------------------------------------


def _canonical_command_names(src_dir: Path) -> list[str]:
    """Return every ``*.md`` in ``src_dir`` in directory order."""
    if not src_dir.is_dir():
        raise FileNotFoundError(f"canonical commands dir missing: {src_dir}")
    names: list[str] = []
    for entry in sorted(src_dir.iterdir(), key=lambda e: e.name):
        if entry.is_file() and entry.suffix == ".md":
            names.append(entry.name)
    return names


def _generate_one_command(
    src_dir: Path,
    name: str,
    command_dir: Path,
    *,
    agent: str,
    skills_dir: str,
    cwd_note: str,
    args_token: str,
) -> GenerateOutcome:
    """Render one canonical command file into ``command_dir``."""
    src = src_dir / name
    dest = command_dir / name
    raw = src.read_text(encoding="utf-8")
    header, body = _split_frontmatter(raw)
    meta = _parse_frontmatter(header)
    if "description" not in meta:
        raise ValueError(f"frontmatter missing description in {src}")
    subtask = meta.get("subtask", "false").lower() == "true"
    rendered = (
        render_opencode_frontmatter(meta["description"], agent, subtask=subtask)
        + substitute(
            body,
            orchestrator_agent=agent,
            skills_dir=skills_dir,
            cwd_note=cwd_note,
            args_token=args_token,
        )
    )
    dest.write_text(rendered, encoding="utf-8")
    return GenerateOutcome(dest=dest, src=src, action=ACTION_GENERATED)


def generate_commands(repo_dir: Path, command_dir: Path) -> list[GenerateOutcome]:
    """Generate one OpenCode slash-command per canonical source ``*.md``.

    The substitution values are the OpenCode defaults. Callers that need a
    different platform should use ``_generate_one_command`` directly with
    their own values.

    Generation is rollback-safe: if a later command raises, every file
    already written by this call is either restored to its pre-existing
    content (when it overwrote something) or removed (when it was
    created), so a partial failure never leaves untracked files.
    """
    src_dir = repo_dir / COMMANDS_SUBDIR
    names = _canonical_command_names(src_dir)
    command_dir.mkdir(parents=True, exist_ok=True)
    outcomes: list[GenerateOutcome] = []
    # Track files this call writes so a later failure can undo them.
    written: list[Path] = []
    # Snapshot pre-existing content BEFORE each write.
    previous: dict[Path, bytes | None] = {}
    try:
        for name in names:
            dest = command_dir / name
            if dest.exists():
                previous[dest] = dest.read_bytes()
            else:
                previous[dest] = None
            # Track the destination BEFORE the call so that a partial
            # write failure inside _generate_one_command still triggers
            # rollback cleanup of the corrupted file.
            written.append(dest)
            outcome = _generate_one_command(
                src_dir,
                name,
                command_dir,
                agent="sdd-orchestrator",
                skills_dir="~/.config/opencode/skills",
                cwd_note=OPENCODE_CWD_NOTE,
                args_token="$ARGUMENTS",
            )
            outcomes.append(outcome)
    except Exception:
        # Rollback in reverse order: restore or remove every file we wrote.
        for dest in reversed(written):
            try:
                prev = previous.get(dest)
                if prev is None:
                    dest.unlink(missing_ok=True)
                else:
                    dest.write_bytes(prev)
            except OSError:
                pass
        raise
    return outcomes


def remove_commands(repo_dir: Path, command_dir: Path) -> list[GenerateOutcome]:
    """Remove every command file the canonical source defines.

    A missing dest is the expected ``absent`` outcome, not an error: only
    an unexpected removal failure raises.
    """
    src_dir = repo_dir / COMMANDS_SUBDIR
    names = _canonical_command_names(src_dir)
    outcomes: list[GenerateOutcome] = []
    for name in names:
        dest = command_dir / name
        try:
            dest.unlink()
            outcomes.append(GenerateOutcome(dest=dest, src=src_dir / name, action=ACTION_REMOVED))
        except FileNotFoundError:
            outcomes.append(GenerateOutcome(dest=dest, src=src_dir / name, action=ACTION_ABSENT))
    return outcomes
