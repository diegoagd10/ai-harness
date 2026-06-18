from __future__ import annotations

import typer

app = typer.Typer()


@app.callback()
def callback() -> None:
    pass


@app.command()
def install() -> None:
    print("Hellow Muppet")


def main() -> None:
    app()
