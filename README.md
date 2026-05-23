# Reels Generator

A **local-first** CLI that turns long-form Arabic course videos into a series of vertical (9:16)
social reels. It transcribes each source video, uses an LLM to select self-contained teaching
moments, then cuts, reframes, captions, and brands each clip.

> No cloud video processing. No auto-publishing. Only transcript **text** is ever sent off-machine
> (to the LLM provider for clip selection).

See [`REELS PIPELINE SPEC.md`](./REELS%20PIPELINE%20SPEC.md) for the full product/technical spec.

## Pipeline

```
ingest → transcribe → select (LLM) → plan-layout → cut → reframe → caption → brand → package
```

Each stage reads a per-video JSON manifest, does its work, writes outputs, and updates the manifest.
Any stage can be resumed with `--from <stage>`.

## Architecture

The codebase follows **Clean Architecture / DDD** layering (dependencies point inward):

```
src/reels/
  domain/          # Entities, Value Objects, domain services, ports (zero framework deps)
  application/     # Use cases (one per stage) + pipeline orchestrator
  infrastructure/  # Adapters: ffprobe, faster-whisper, OpenAI/Claude, OpenCV, libass, config, persistence
  presentation/    # Typer CLI + composition root (dependency wiring)
```

- Domain ports (`Transcriber`, `ClipSelector`, `PresenterDetector`, …) are defined inside the
  domain/application layers; infrastructure provides the implementations.
- The CLI is the only composition root — it wires concrete adapters into use cases.

## Requirements

- **macOS on Apple Silicon** (Intel falls back to CPU with a logged slowdown warning).
- **Python 3.12** (managed via [`uv`](https://docs.astral.sh/uv/)).
- **FFmpeg with libass** for subtitle burn-in.

  > ⚠️ The current Homebrew `ffmpeg` (8.x) ships **without libass** — and neither the core nor the
  > `homebrew-ffmpeg` tap formula exposes a `--with-libass` option anymore. A libass-enabled build
  > is required for the **caption** and **brand** stages (not for ingest/transcribe/cut/reframe).
  >
  > Compile one from source against Homebrew's libass (≈10–15 min), then point `paths.ffmpeg` at it:
  >
  > ```bash
  > brew install libass x264 pkg-config
  > # configure with --enable-gpl --enable-libx264 --enable-libass --enable-libfreetype \
  > #   --enable-libfontconfig --enable-libfribidi --enable-libharfbuzz, install under ./vendor/ffmpeg
  > ```
  >
  > Set `paths.ffmpeg: ./vendor/ffmpeg/bin/ffmpeg` in `config.yaml`. The CLI checks libass capability
  > at startup and fails fast (with remediation) only when a stage that needs it actually runs;
  > `reels doctor` shows the status.

## Setup

```bash
uv sync                       # creates .venv and installs everything

# Provide your LLM key via a .env file (only transcript TEXT is ever sent):
cp .env.example .env          # then edit .env and fill in your key
```

### Selection provider (clip selection stage)

Set `selection.provider` in `config.yaml`. DeepSeek and OpenAI share one adapter (they're
OpenAI-API-compatible — they differ only by `base_url` and key), so switching is config-only:

| provider | key env (in `.env`) | default model | notes |
|---|---|---|---|
| `deepseek` (default) | `DEEPSEEK_API_KEY` | `deepseek-chat` | OpenAI-compatible; `base_url=https://api.deepseek.com` |
| `openai` | `OPENAI_API_KEY` | `gpt-4o` | OpenAI-compatible |
| `claude` | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` | Anthropic SDK |

The exact model id is whatever your account exposes — set `selection.model` (or `REELS_SELECTION_MODEL`
in `.env`). You can also override the endpoint via `selection.base_url` / `REELS_SELECTION_BASE_URL`.

## Usage

```bash
# Run the whole pipeline over the input folder:
uv run reels run --config config.yaml

# Resume from a specific stage (re-uses prior stage outputs from the manifest):
uv run reels run --from select --config config.yaml

# Resume between a range of stages (e.g. just transcribe):
uv run reels run --from transcribe --to transcribe

# Process only specific reels (per-reel stages):
uv run reels run --from plan-layout --to package --reel 3 --reel 7

# Inspect environment / dependency health:
uv run reels doctor
```

Configuration lives in [`config.yaml`](./config.yaml) (see spec §7). Secrets are env-vars only.

## Web app — Reels Studio

A local browser UI to drive and visualize the whole pipeline (spec:
[`WEB_APP_SPEC.md`](./WEB_APP_SPEC.md)). It's a FastAPI delivery adapter that reuses the same
use cases as the CLI (no business logic in the web tier) plus a React/Vite SPA.

```bash
uv sync --extra web           # install the web dependencies (FastAPI, uvicorn, …)

# Build the SPA once (outputs web/dist, which the server serves):
cd web && npm install && npm run build && cd ..

uv run --extra web reels web  # → http://127.0.0.1:8000
```

What you can do in the browser:

- **Library** — video cards with poster thumbnails + per-stage badges; scan the input folder.
- **Video detail** — the original player with **reel markers on the timeline** (click a block to play
  that span; it auto-stops at the reel's end); a reels panel; and the **transcript** synced to playback.
- **Pipeline** — run any stage range, all reels, or a single reel, with **live per-stage progress** (SSE).
- **Reels** — preview/download finished reels, and **trim/split + edit** hook/caption or **delete** a reel.
- **Config** — edit all of `config.yaml` from a form (secrets stay in `.env`); a Health/Doctor panel.
- **Gallery** — every finished reel with inline players and downloads.
- **Generate preview** — transcodes a browser-friendly proxy so `.mov`/PCM sources play with audio in Chrome.

> Dev mode (hot reload): run `uv run --extra web reels web` in one terminal and `npm run dev` in
> `web/` in another — Vite proxies `/api` to the backend at :8000.

## Build status

Built in thin slices per spec §10, stopping at each human checkpoint:

- [x] **Slice 1** — Skeleton + ingest + transcribe (word-level transcript JSON).
- [x] **Slice 2** — Select (LLM clip selection; DeepSeek/OpenAI/Claude; validated + reconciled).
- [x] **Slice 3** — Cut + MODE A reframe (OpenCV presenter detection → 9:16 presenter crop; `--reel` filter).
- [x] **Slice 4** — Arabic captions (word-by-word `{\k}` karaoke via libass; shaping/bidi/code-switch verified by the harness).
- [x] **Slice 5** — Brand (intro/outro concat + logo overlay) + package (`{source}__NN__{slug}.mp4` + `reels.json`/`reels.md`).
- [x] **Slice 6/7** — Loop over clips / folder (`reels run` processes all reels and all input videos; `--reel` narrows).
- [ ] Slice 8 — MODE B (stacked slides + presenter).

Plus **Reels Studio** — the web UI (see above and [`WEB_APP_SPEC.md`](./WEB_APP_SPEC.md)).
