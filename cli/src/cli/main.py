import typer
from rich.console import Console

app = typer.Typer()
console = Console()


@app.callback()
def callback() -> None:
    pass


@app.command()
def install() -> None:
    console.print("hello muppet")


def main() -> None:
    app()
