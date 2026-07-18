"""Reels Generator CLI — a thin launcher. Bare `reels` starts the Reels Studio web app,
which is the only way to run the pipeline; `reels doctor` checks environment health.
All business logic lives inward (application/domain).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from reels.presentation.container import Container

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="Reels Studio — turn long-form Arabic course videos into vertical (9:16) social reels.",
)
console = Console()

DEFAULT_CONFIG = Path("config.yaml")


@app.callback()
def main(
    ctx: typer.Context,
    config: Annotated[Path, typer.Option(help="Path to config.yaml.")] = DEFAULT_CONFIG,
    host: Annotated[str, typer.Option(help="Bind host.")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port.")] = 8000,
) -> None:
    """Launch the Reels Studio web app — the only interface to the pipeline."""
    if ctx.invoked_subcommand is not None:
        return

    import uvicorn

    from reels.presentation.api import app as api_app

    console.print(f"[green]Reels Studio →[/green] http://{host}:{port}")
    uvicorn.run(api_app.create_app(config.resolve()), host=host, port=port)


@app.command()
def doctor(
    config: Annotated[Path, typer.Option(help="Path to config.yaml.")] = DEFAULT_CONFIG,
) -> None:
    """Check the environment and configuration health."""
    table = Table(title="Reels Generator — environment", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    try:
        container = Container.from_config(config)
        table.add_row("config", "[green]ok", str(config))
    except Exception as exc:  # noqa: BLE001 — doctor reports any failure rather than crashing
        table.add_row("config", "[red]fail", str(exc))
        console.print(table)
        raise typer.Exit(code=1) from exc

    settings = container.settings
    status = container.media_environment.status()

    _row(table, "ffprobe", status.ffprobe_path is not None, status.ffprobe_path or "not found")
    _row(table, "ffmpeg", status.ffmpeg_path is not None, status.version or "not found")
    _row(
        table,
        "ffmpeg libass",
        status.has_libass,
        "subtitle burn-in available"
        if status.has_libass
        else "MISSING — needed for caption/brand stages (see README)",
    )
    _row(table, "videotoolbox", status.has_videotoolbox, "hw accel available")
    _row(
        table,
        "input dir",
        settings.paths.input_dir.exists(),
        str(settings.paths.input_dir),
    )
    _row(table, "font", settings.paths.font.exists(), str(settings.paths.font))

    prov = container.provider
    table.add_row(
        "selection",
        "[green]ok",
        f"{prov.provider} · model={prov.model}" + (f" · {prov.base_url}" if prov.base_url else ""),
    )
    _row(
        table,
        f"{prov.provider} key",
        bool(os.environ.get(prov.key_env)),
        f"${prov.key_env} {'set' if os.environ.get(prov.key_env) else 'NOT set'}",
    )

    console.print(table)


def _row(table: Table, name: str, ok: bool, detail: str) -> None:
    table.add_row(name, "[green]ok" if ok else "[red]fail", detail)


if __name__ == "__main__":
    app()
