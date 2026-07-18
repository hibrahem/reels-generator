# Web UI Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Reels Studio (the web app) the only interface: bare `reels` launches the server, the `run` and `web` CLI commands disappear, web dependencies become required, and the README documents the web-only flow.

**Architecture:** Only the presentation entry point and packaging change. `cli.py` shrinks to a Typer callback (server launcher) plus the existing `doctor` command. Domain/application/infrastructure/API layers are untouched.

**Tech Stack:** Typer, uvicorn, FastAPI (existing), uv for packaging, pytest with `typer.testing.CliRunner`.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-19-web-ui-only-design.md` (approved).
- Beads issue: `rg-oq8`.
- Defaults must match today's `reels web`: config `config.yaml`, host `127.0.0.1`, port `8000`.
- No changes under `src/reels/domain`, `src/reels/application`, `src/reels/infrastructure`, `src/reels/presentation/api`, or `web/`.
- Run all commands from the repo root (the worktree).

---

### Task 1: Promote web dependencies to required

**Files:**
- Modify: `pyproject.toml:4` (description), `pyproject.toml:10-40` (dependencies + extra removal)
- Modify: `uv.lock` (regenerated, not hand-edited)

**Interfaces:**
- Produces: `import uvicorn` and `from reels.presentation.api.app import create_app` work in the default environment (no `--extra web`). Task 2's cli.py relies on this.

- [ ] **Step 1: Edit pyproject.toml**

Change the description line to:

```toml
description = "Local-first web app that turns long-form Arabic course videos into vertical (9:16) social reels."
```

In `dependencies`, change the comment `# Presentation (CLI)` to `# Presentation (CLI launcher + terminal doctor)` and append a new group at the end of the list:

```toml
    # Presentation (web — Reels Studio, the only pipeline interface)
    "fastapi>=0.115",
    "python-multipart>=0.0.9",
    "sse-starlette>=2.1",
    "uvicorn[standard]>=0.30",
```

Delete the entire `[project.optional-dependencies]` table (the `web` extra is its only member).

- [ ] **Step 2: Regenerate the lockfile and sync**

Run: `uv sync`
Expected: resolves and installs without error; `uv.lock` modified.

- [ ] **Step 3: Verify web deps import in the default env**

Run: `uv run python -c "import uvicorn; from reels.presentation.api.app import create_app; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: make web dependencies required (web UI is the only interface)"
```

---

### Task 2: `reels` launches the Studio; `run`/`web` commands removed

**Files:**
- Modify: `src/reels/presentation/cli.py` (full rewrite, content below)
- Test: `tests/presentation/test_cli.py` (new; `tests/presentation/` has no `__init__.py` convention — match the other test dirs: check `ls tests/api` first and copy its layout)

**Interfaces:**
- Consumes: `create_app(config_path: Path) -> FastAPI` from `reels.presentation.api.app` (existing); web deps installed by Task 1.
- Produces: console script `reels` whose bare invocation calls `uvicorn.run(create_app(config.resolve()), host=host, port=port)`; subcommand `doctor` unchanged.

- [ ] **Step 1: Write the failing tests**

Create `tests/presentation/test_cli.py`:

```python
"""Feature tests for the CLI: bare `reels` launches Reels Studio; the pipeline
is not runnable from the command line."""

from typer.testing import CliRunner

from reels.presentation import cli

runner = CliRunner()


def test_bare_reels_launches_the_studio_server(monkeypatch, tmp_path):
    captured = {}

    def fake_uvicorn_run(asgi_app, host, port):
        captured["asgi_app"] = asgi_app
        captured["host"] = host
        captured["port"] = port

    def fake_create_app(config_path):
        captured["config"] = config_path
        return "asgi-app"

    monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)
    monkeypatch.setattr("reels.presentation.api.app.create_app", fake_create_app)

    config = tmp_path / "config.yaml"
    config.write_text("paths: {}\n")

    result = runner.invoke(cli.app, ["--config", str(config), "--port", "9000"])

    assert result.exit_code == 0
    assert captured["asgi_app"] == "asgi-app"
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9000
    assert captured["config"] == config.resolve()


def test_pipeline_cannot_be_run_from_the_command_line():
    result = runner.invoke(cli.app, ["run"])
    assert result.exit_code != 0


def test_web_subcommand_is_gone_because_it_is_the_default():
    result = runner.invoke(cli.app, ["web"])
    assert result.exit_code != 0


def test_doctor_command_still_exists():
    result = runner.invoke(cli.app, ["doctor", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/presentation/test_cli.py -v`
Expected: `test_bare_reels_launches_the_studio_server`, `test_pipeline_cannot_be_run_from_the_command_line`, and `test_web_subcommand_is_gone_because_it_is_the_default` FAIL against the current CLI (bare invocation shows help/exits 2; `run` and `web` exist and exit 0 or fail differently). `test_doctor_command_still_exists` may already pass.

- [ ] **Step 3: Rewrite cli.py**

Replace `src/reels/presentation/cli.py` with:

```python
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
```

Note the doctor body and `_row` are copied verbatim from the current file — only `run`, `web`, `_load`, `_preflight`, `_print_progress`, `_print_summary`, `_clock`, `_configure_logging`, and the now-unused imports (`logging`, pipeline/Stage/LLM-error imports, `_LIBASS_STAGES`) are gone.

The test monkeypatches `reels.presentation.api.app.create_app`, so the callback must resolve `create_app` at call time through the module (`api_app.create_app(...)`), not bind it with `from ... import create_app`.

- [ ] **Step 4: Run the CLI tests**

Run: `uv run pytest tests/presentation/test_cli.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Run the full suite + lint**

Run: `uv run pytest -q && uv run ruff check src tests`
Expected: all tests pass, no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/reels/presentation/cli.py tests/presentation/test_cli.py
git commit -m "feat: bare 'reels' launches Reels Studio; remove the run/web commands"
```

---

### Task 3: README — document the web-only flow

**Files:**
- Modify: `README.md` (edits below, by current line numbers)

**Interfaces:** none (docs only).

- [ ] **Step 1: Apply the edits**

1. **Intro (line 3):** replace `A **local-first** CLI (and optional web UI) that turns` with `A **local-first** web app — **Reels Studio** — that turns`.

2. **Quick Start (lines 18-37):** replace the code block and the "Prefer a browser UI?" line with:

```bash
# 1. Install Python deps (creates .venv)
uv sync

# 2. Build the Reels Studio SPA once (outputs web/dist, which the server serves)
cd web && npm install && npm run build && cd ..

# 3. Build ffmpeg-with-libass into ./vendor (one-time, ~10–15 min — see "FFmpeg with libass")
#    Homebrew's ffmpeg does NOT include libass, which the caption/brand stages need.

# 4. Add your LLM key (only transcript TEXT is ever sent off-machine)
cp .env.example .env        # then edit .env and paste your key

# 5. Verify everything is wired up — do this FIRST, it fails fast with fixes
uv run reels doctor

# 6. Drop one or more source videos into ./input, then launch the Studio
uv run reels                # → http://127.0.0.1:8000

# → run the pipeline from the Studio's Pipeline tab; finished reels land in ./output
#   as {source}__NN__{slug}.mp4 (+ {source}.reels.json / {source}.reels.md)
```

3. **Pipeline (line 48):** replace `Any stage can be resumed with `--from <stage>` (and stopped early with `--to <stage>`).` with `Any stage range can be run or resumed from the Studio's **Pipeline** tab (equivalent to from/to stage selection), and any stage can be redone from the video page.`

4. **Architecture (line 59):** replace the `presentation/` line with:

```
  presentation/    # FastAPI web adapter + thin Typer launcher (reels / reels doctor) + composition root
```

   And (line 64) replace `- The CLI/web layer is the only composition root — it wires concrete adapters into use cases.` with `- The presentation layer is the only composition root — it wires concrete adapters into use cases.`

5. **FFmpeg with libass (line 84):** replace `the CLI checks libass at startup and fails fast (with remediation) only when a stage` with `the pipeline checks libass and fails fast (with remediation) only when a stage`.

6. **Setup (lines 119-126):** in the code block, after the `uv sync` line add:

```bash
cd web && npm install && npm run build && cd ..   # build the Studio SPA (served by the app)
```

7. **Input (lines 151-157):** replace ``reels run` processes every video it finds there.` with `The Studio's pipeline processes every video it finds there.` and change the example's last line from `uv run reels run` to `uv run reels`.

8. **Usage (lines 159-184):** replace the whole section body with:

```markdown
​```bash
uv run reels                                  # launch Reels Studio → http://127.0.0.1:8000
uv run reels --host 0.0.0.0 --port 9000       # bind elsewhere
uv run reels --config path/to/config.yaml     # non-default config
uv run reels doctor                           # inspect environment / dependency health
​```

Everything else — running stage ranges, single reels, resume/redo, editing — happens in the
browser (see [Reels Studio](#web-app--reels-studio) below).

Configuration lives in [`config.yaml`](./config.yaml) (see spec §7). Secrets are env-vars only.
```

(Write the code fences plainly — the `​` marks above are only to nest them in this plan.)

9. **Web app section (lines 204-213):** replace the setup code block and the "Bind elsewhere" line with:

```bash
# Build the SPA once (outputs web/dist, which the server serves):
cd web && npm install && npm run build && cd ..

uv run reels                  # → http://127.0.0.1:8000
```

   And update the intro sentence (line 201-202): replace `It's a FastAPI delivery adapter that reuses the same use cases as the CLI (no business logic in the web tier) plus a React/Vite SPA.` with `It's a FastAPI delivery adapter over the application-layer use cases (no business logic in the web tier) plus a React/Vite SPA.`

10. **Dev mode note (line 226):** replace `uv run --extra web reels web` with `uv run reels`.

11. **Troubleshooting (line 237, 239):** replace `| `reels run` finds no videos |` with `| The pipeline finds no videos |`, and in the "Want to re-run cleanly" row replace `or use `--from <stage>` to redo from a point.` with `or use the Studio's stage **redo** to re-run from a point.`

12. **Build status (line 250):** replace `(`reels run` processes all reels and all input videos; `--reel` narrows)` with `(the pipeline processes all reels and all input videos; a single reel can be targeted)`.

- [ ] **Step 2: Sanity-check for stale references**

Run: `grep -n "reels run\|--extra web\|reels web" README.md`
Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README documents the web-only flow"
```

---

### Task 4: End-to-end verification and close-out

**Files:** none (verification only).

- [ ] **Step 1: Doctor still works**

Run: `uv run reels doctor`
Expected: the environment table renders (some rows may be red on this machine — that's fine; it must not crash).

- [ ] **Step 2: Launch the Studio and load it**

Ensure `web/dist` exists (`cd web && npm install && npm run build && cd ..` if not), then start `uv run reels` in the background and fetch `http://127.0.0.1:8000/` — expect HTTP 200 with the SPA's HTML, and `GET /api/...` health/system endpoint responding. Stop the server afterwards.

- [ ] **Step 3: Close the beads issue and finish**

```bash
bd close rg-oq8 --reason="Web UI is the only interface: bare reels launches Studio, run/web removed, web deps required, README rewritten"
bd dolt pull
git status
```

Then follow the session close protocol (commit any stragglers).
