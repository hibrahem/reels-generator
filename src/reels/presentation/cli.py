"""Reels Generator CLI — the delivery mechanism. Thin: it parses input, drives the orchestrator,
and presents results. All business logic lives inward (application/domain).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from reels.application.pipeline import PipelineProgress, StageNotBuilt
from reels.application.pipeline_stage import Stage
from reels.infrastructure.llm.clip_json import MalformedSelectionResponse
from reels.infrastructure.llm.errors import SelectionUnavailable
from reels.presentation.container import Container

app = typer.Typer(
    add_completion=False,
    help="Turn long-form Arabic course videos into vertical (9:16) social reels.",
)
console = Console()

DEFAULT_CONFIG = Path("config.yaml")

# Stages that require a libass-enabled FFmpeg.
_LIBASS_STAGES = {Stage.CAPTION, Stage.BRAND}


@app.command()
def run(
    config: Annotated[Path, typer.Option(help="Path to config.yaml.")] = DEFAULT_CONFIG,
    from_stage: Annotated[
        Stage, typer.Option("--from", help="Resume from this stage.")
    ] = Stage.INGEST,
    to_stage: Annotated[
        Stage, typer.Option("--to", help="Stop after this stage.")
    ] = Stage.PACKAGE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run the pipeline over the configured input folder."""
    _configure_logging(verbose)
    container = _load(config)
    _preflight(container, from_stage, to_stage)

    console.rule(f"[bold]Running pipeline: {from_stage.value} → {to_stage.value}")
    try:
        manifests = container.orchestrator.run(
            from_stage=from_stage, to_stage=to_stage, on_progress=_print_progress
        )
    except StageNotBuilt as exc:
        console.print(f"\n[yellow]⏸  {exc}")
        console.print("[dim]This is expected — later pipeline slices are not built yet.")
        raise typer.Exit(code=0) from exc
    except SelectionUnavailable as exc:
        console.print(f"[red]✗ {exc}")
        raise typer.Exit(code=1) from exc
    except MalformedSelectionResponse as exc:
        console.print(f"[red]✗ The selection model returned unparseable JSON: {exc}")
        raise typer.Exit(code=1) from exc
    except FileNotFoundError as exc:
        console.print(f"[red]✗ {exc}")
        raise typer.Exit(code=1) from exc

    _print_summary(manifests)


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


# --- helpers -----------------------------------------------------------------------------------


def _load(config: Path) -> Container:
    try:
        return Container.from_config(config)
    except FileNotFoundError as exc:
        console.print(f"[red]✗ {exc}")
        raise typer.Exit(code=1) from exc


def _preflight(container: Container, from_stage: Stage, to_stage: Stage) -> None:
    """Fail fast only when a requested stage actually needs a capability that is missing."""
    requested = {s for s in Stage if from_stage <= s <= to_stage}
    if requested & _LIBASS_STAGES:
        status = container.media_environment.status()
        if not status.has_libass:
            console.print(
                "[red]✗ The caption/brand stages need an FFmpeg built with libass, "
                "but this FFmpeg lacks it."
            )
            console.print(
                "[yellow]Fix: brew tap homebrew-ffmpeg/ffmpeg && "
                "brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-libass --with-fontconfig "
                "--with-freetype --with-fribidi"
            )
            raise typer.Exit(code=1)


def _print_progress(progress: PipelineProgress) -> None:
    console.print(
        f"[green]✓[/green] [bold]{progress.stage.value:<10}[/bold] "
        f"{progress.source_id}  [dim]{progress.message}"
    )


def _print_summary(manifests: list) -> None:
    console.rule("[bold]Summary")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Source")
    table.add_column("Stages done")
    table.add_column("Transcript")
    table.add_column("Reels")
    table.add_column("Warnings")
    for m in manifests:
        table.add_row(
            m.source.id.value,
            ", ".join(s.value for s in m.completed_stages),
            m.transcript_path.name if m.transcript_path else "—",
            str(len(m.reels)),
            str(len(m.warnings)),
        )
    console.print(table)

    reels = [(m, r) for m in manifests for r in m.reels]
    if reels:
        rt = Table(title="Selected reels", show_header=True, header_style="bold")
        rt.add_column("#")
        rt.add_column("Start–End")
        rt.add_column("Dur")
        rt.add_column("Conf")
        rt.add_column("Title")
        rt.add_column("Hook")
        for _, r in reels:
            tr = r.candidate.time_range
            rt.add_row(
                f"{r.index:02d}",
                f"{_clock(tr.start)}–{_clock(tr.end)}",
                f"{tr.duration:.0f}s",
                f"{float(r.candidate.confidence):.2f}",
                r.candidate.title[:30],
                r.candidate.hook[:42],
            )
        console.print(rt)

    for m in manifests:
        for warning in m.warnings:
            console.print(f"[yellow]⚠ {m.source.id.value}: {warning}")


def _clock(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _row(table: Table, name: str, ok: bool, detail: str) -> None:
    table.add_row(name, "[green]ok" if ok else "[red]fail", detail)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


if __name__ == "__main__":
    app()
