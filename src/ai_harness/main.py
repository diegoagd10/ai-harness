import shutil
from pathlib import Path

import typer
from rich.console import Console

from ai_harness import compat
from ai_harness.rendering import render_dispatcher
from ai_harness.sdd import SddError, resolve

app = typer.Typer()
console = Console()

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
AGENTS_MD_SRC = RESOURCES_DIR / "AGENTS.md"
SKILLS_SRC = RESOURCES_DIR / "skills"
OPENCODE_JSON_SRC = RESOURCES_DIR / "agent-clis" / "opencode" / "opencode.json"
OPENCODE_SDD_PROMPTS_SRC = RESOURCES_DIR / "prompts" / "sdd"

AGENTS_MD_TARGETS = (
    Path(".agents/AGENTS.md"),
    Path(".claude/CLAUDE.md"),
    Path(".copilot/copilot-instructions.md"),
)

SKILLS_TARGET_DIRS = (
    Path(".agents/skills"),
    Path(".claude/skills"),
)

OPENCODE_JSON_TARGET = Path(".config/opencode/opencode.json")
OPENCODE_JSON_BACKUP_TARGET = Path(".config/opencode/opencode.json.ai-harness-backup")
OPENCODE_AGENTS_MD_TARGET = Path(".config/opencode/AGENTS.md")
OPENCODE_AGENTS_MD_BACKUP_TARGET = Path(".config/opencode/AGENTS.md.ai-harness-backup")
OPENCODE_SDD_PROMPTS_TARGET_DIR = Path(".config/opencode/prompts/sdd")
OPENCODE_BACKUP_SUFFIX = ".ai-harness-backup"
OPENCODE_CONFLICT_BACKUP_SUFFIX = ".ai-harness-conflict-backup"


@app.callback()
def callback() -> None:
    pass


def next_available_path(path: Path) -> Path:
    if not path.exists():
        return path

    index = 1
    while True:
        candidate = path.with_name(f"{path.name}.{index}")
        if not candidate.exists():
            return candidate
        index += 1


@app.command()
def install() -> None:
    home = Path.home()

    for relative_target in AGENTS_MD_TARGETS:
        target = home / relative_target
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(AGENTS_MD_SRC, target)
        console.print(f"Installed {target}")

    for relative_dir in SKILLS_TARGET_DIRS:
        target_dir = home / relative_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir in SKILLS_SRC.iterdir():
            if not skill_dir.is_dir():
                continue
            target = target_dir / skill_dir.name
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(skill_dir, target)
        console.print(f"Installed skills to {target_dir}")

    opencode_json_target = home / OPENCODE_JSON_TARGET
    opencode_json_target.parent.mkdir(parents=True, exist_ok=True)
    opencode_json = OPENCODE_JSON_SRC.read_text(encoding="utf-8").replace(
        "{{HOME}}", str(home)
    )
    opencode_json_backup = home / OPENCODE_JSON_BACKUP_TARGET
    if opencode_json_target.exists() and opencode_json_target.read_text(
        encoding="utf-8"
    ) != opencode_json:
        if not opencode_json_backup.exists():
            shutil.copyfile(opencode_json_target, opencode_json_backup)
            console.print(f"Backed up {opencode_json_target} to {opencode_json_backup}")
        else:
            conflict_backup = next_available_path(
                opencode_json_target.with_name(
                    f"{opencode_json_target.name}{OPENCODE_CONFLICT_BACKUP_SUFFIX}"
                )
            )
            shutil.copyfile(opencode_json_target, conflict_backup)
            console.print(f"Backed up {opencode_json_target} to {conflict_backup}")
    opencode_json_target.write_text(opencode_json, encoding="utf-8")
    console.print(f"Installed {opencode_json_target}")

    opencode_agents_md_target = home / OPENCODE_AGENTS_MD_TARGET
    opencode_agents_md_backup = home / OPENCODE_AGENTS_MD_BACKUP_TARGET
    agents_md = AGENTS_MD_SRC.read_text(encoding="utf-8")
    if opencode_agents_md_target.exists() and opencode_agents_md_target.read_text(
        encoding="utf-8"
    ) != agents_md:
        if not opencode_agents_md_backup.exists():
            shutil.copyfile(opencode_agents_md_target, opencode_agents_md_backup)
            console.print(
                f"Backed up {opencode_agents_md_target} to {opencode_agents_md_backup}"
            )
        else:
            conflict_backup = next_available_path(
                opencode_agents_md_target.with_name(
                    f"{opencode_agents_md_target.name}{OPENCODE_CONFLICT_BACKUP_SUFFIX}"
                )
            )
            shutil.copyfile(opencode_agents_md_target, conflict_backup)
            console.print(
                f"Backed up {opencode_agents_md_target} to {conflict_backup}"
            )
    opencode_agents_md_target.write_text(agents_md, encoding="utf-8")
    console.print(f"Installed {opencode_agents_md_target}")

    opencode_prompts_target_dir = home / OPENCODE_SDD_PROMPTS_TARGET_DIR
    opencode_prompts_target_dir.mkdir(parents=True, exist_ok=True)
    for prompt_file in OPENCODE_SDD_PROMPTS_SRC.iterdir():
        if not prompt_file.is_file():
            continue
        target = opencode_prompts_target_dir / prompt_file.name
        backup = target.with_name(f"{target.name}{OPENCODE_BACKUP_SUFFIX}")
        prompt_content = prompt_file.read_text(encoding="utf-8")
        if target.exists() and target.read_text(
            encoding="utf-8"
        ) != prompt_content:
            if not backup.exists():
                shutil.copyfile(target, backup)
                console.print(f"Backed up {target} to {backup}")
            else:
                conflict_backup = next_available_path(
                    target.with_name(
                        f"{target.name}{OPENCODE_CONFLICT_BACKUP_SUFFIX}"
                    )
                )
                shutil.copyfile(target, conflict_backup)
                console.print(f"Backed up {target} to {conflict_backup}")
        target.write_text(prompt_content, encoding="utf-8")
    console.print(f"Installed opencode SDD prompts to {opencode_prompts_target_dir}")


@app.command()
def uninstall() -> None:
    home = Path.home()

    for relative_target in AGENTS_MD_TARGETS:
        target = home / relative_target
        if target.exists():
            target.unlink()
            console.print(f"Removed {target}")

    project_skill_names = [d.name for d in SKILLS_SRC.iterdir() if d.is_dir()]

    for relative_dir in SKILLS_TARGET_DIRS:
        target_dir = home / relative_dir
        for skill_name in project_skill_names:
            target = target_dir / skill_name
            if target.exists():
                shutil.rmtree(target)
                console.print(f"Removed {target}")

    opencode_json_target = home / OPENCODE_JSON_TARGET
    opencode_json_backup = home / OPENCODE_JSON_BACKUP_TARGET
    opencode_json = OPENCODE_JSON_SRC.read_text(encoding="utf-8").replace(
        "{{HOME}}", str(home)
    )
    if opencode_json_target.exists() and opencode_json_target.read_text(
        encoding="utf-8"
    ) == opencode_json:
        opencode_json_target.unlink()
        console.print(f"Removed {opencode_json_target}")
    if not opencode_json_target.exists() and opencode_json_backup.exists():
        shutil.move(opencode_json_backup, opencode_json_target)
        console.print(f"Restored {opencode_json_target} from {opencode_json_backup}")

    opencode_agents_md_target = home / OPENCODE_AGENTS_MD_TARGET
    opencode_agents_md_backup = home / OPENCODE_AGENTS_MD_BACKUP_TARGET
    agents_md = AGENTS_MD_SRC.read_text(encoding="utf-8")
    if opencode_agents_md_target.exists() and opencode_agents_md_target.read_text(
        encoding="utf-8"
    ) == agents_md:
        opencode_agents_md_target.unlink()
        console.print(f"Removed {opencode_agents_md_target}")
    if not opencode_agents_md_target.exists() and opencode_agents_md_backup.exists():
        shutil.move(opencode_agents_md_backup, opencode_agents_md_target)
        console.print(
            f"Restored {opencode_agents_md_target} from {opencode_agents_md_backup}"
        )

    opencode_prompts_target_dir = home / OPENCODE_SDD_PROMPTS_TARGET_DIR
    for prompt_file in OPENCODE_SDD_PROMPTS_SRC.iterdir():
        if not prompt_file.is_file():
            continue
        target = opencode_prompts_target_dir / prompt_file.name
        backup = target.with_name(f"{target.name}{OPENCODE_BACKUP_SUFFIX}")
        prompt_content = prompt_file.read_text(encoding="utf-8")
        if target.exists() and target.read_text(encoding="utf-8") == prompt_content:
            target.unlink()
            console.print(f"Removed {target}")
        if not target.exists() and backup.exists():
            shutil.move(backup, target)
            console.print(f"Restored {target} from {backup}")


def _run_sdd_resolve(
    cwd: str,
    workspace_root: str,
    change_name: str,
    include_instructions: bool,
    json_output: bool,
) -> None:
    """Resolve status, then emit JSON (when json_output) or dispatcher markdown.

    Resolution errors (SddError) and OSError are caught, reported to stderr,
    and exit 1. JSON output goes through compat.status_to_json; markdown
    output goes through render_dispatcher.
    """
    try:
        status = resolve(cwd, workspace_root, change_name, include_instructions=include_instructions)
    except SddError as err:
        typer.echo(f"ai-harness: {err}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR) from err
    except OSError as err:
        typer.echo(f"ai-harness: {err}", err=True)
        raise typer.Exit(code=compat.EXIT_ERROR) from err

    if json_output:
        typer.echo(compat.status_to_json(status))
    else:
        typer.echo(render_dispatcher(status))


@app.command(name="sdd-status")
def sdd_status(
    change: str | None = typer.Argument(
        None, help="Active OpenSpec change name; inferred when omitted."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of a rendered summary."
    ),
    instructions: bool = typer.Option(
        False, "--instructions", help="Include phase instructions in JSON output."
    ),
    cwd: str = typer.Option("", "--cwd", help="Workspace directory to read openspec/ from."),
) -> None:
    """Report the SDD phase state for a change."""
    _run_sdd_resolve(
        cwd=cwd,
        workspace_root="",
        change_name=change or "",
        include_instructions=instructions,
        json_output=True,  # sdd-status always emits JSON in this slice
    )


@app.command(name="sdd-continue")
def sdd_continue(
    change: str | None = typer.Argument(
        None, help="Active OpenSpec change name; inferred when omitted."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit deterministic JSON instead of dispatcher markdown."
    ),
    cwd: str = typer.Option("", "--cwd", help="Workspace directory to read openspec/ from."),
) -> None:
    """Show the next SDD action and per-phase instructions (dispatcher markdown by default)."""
    _run_sdd_resolve(
        cwd=cwd,
        workspace_root="",
        change_name=change or "",
        include_instructions=True,
        json_output=json_output,
    )


def main() -> None:
    app()
