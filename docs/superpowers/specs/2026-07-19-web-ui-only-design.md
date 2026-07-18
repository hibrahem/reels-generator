# Web UI as the Only Interface

**Date:** 2026-07-19
**Status:** Approved
**Beads issue:** rg-oq8

## Problem

The project exposes two ways to drive the pipeline: the `reels run` Typer command and the
Reels Studio web app (`reels web`). Maintaining two delivery mechanisms doubles the surface
for presentation bugs, and the web app is now the richer of the two (job progress, transcript
editing, stage redo, silence remover). Decision: the web UI becomes the only interface.

## Decision

`reels` with no subcommand launches Reels Studio. The `run` command is deleted; the pipeline
is driven exclusively through the web app's job API. `reels doctor` survives as a terminal
environment check.

## Design

### CLI (`src/reels/presentation/cli.py`)

- A Typer callback with `invoke_without_command=True` replaces the `web` subcommand: bare
  `reels` starts uvicorn with `create_app(config)`. Options `--config` (default
  `config.yaml`), `--host` (default `127.0.0.1`), `--port` (default `8000`) — identical to
  today's `reels web`.
- `run` and its console-presentation helpers (`_load`, `_preflight`, `_print_progress`,
  `_print_summary`, `_clock`, `_configure_logging`) are deleted.
- `doctor` is unchanged (keeps `_row`).
- The ImportError fallback for missing web dependencies is removed — web deps are required.

### Packaging (`pyproject.toml`)

- `fastapi`, `python-multipart`, `sse-starlette`, `uvicorn[standard]` move from the `web`
  optional-dependency extra into `[project] dependencies`; the extra is removed.
- Project description becomes "Local-first web app that turns long-form Arabic course videos
  into vertical (9:16) social reels."
- `uv.lock` regenerated via `uv sync`.

### README

Rewritten around a single flow: `uv sync` → `cd web && npm install && npm run build` →
`uv run reels`. All `reels run` examples (`--from/--to/--reel`, resume docs) are removed;
stage resume/redo is described as a Studio feature. Doctor, requirements, provider
configuration, and troubleshooting sections stay (troubleshooting rows referencing
`reels run` are reworded for the web flow).

## Out of Scope

- No changes to domain, application, infrastructure, or API layers.
- No changes to the React SPA.
- Doctor checks are not moved into the web UI.

## Verification

- Full pytest suite passes.
- `uv run reels` launches, Studio loads in the browser, and `reels doctor` still works.
