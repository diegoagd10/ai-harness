import shutil
from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer()
console = Console()

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
AGENTS_MD_SRC = RESOURCES_DIR / "AGENTS.md"
SKILLS_SRC = RESOURCES_DIR / "skills"

AGENTS_MD_TARGETS = (
    Path(".agents/AGENTS.md"),
    Path(".claude/CLAUDE.md"),
    Path(".copilot/copilot-instructions.md"),
)

SKILLS_TARGET_DIRS = (
    Path(".agents/skills"),
    Path(".claude/skills"),
)


@app.callback()
def callback() -> None:
    pass


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


def main() -> None:
    app()
