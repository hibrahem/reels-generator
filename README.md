# Reels Generator

A **local-first** CLI (and optional web UI) that turns long-form Arabic course videos into a series
of vertical (9:16) social reels. It transcribes each source video, uses an LLM to select
self-contained teaching moments, then cuts, reframes, captions, and brands each clip.

> No cloud video processing. No auto-publishing. Only transcript **text** is ever sent off-machine
> (to the LLM provider for clip selection).

See [`REELS PIPELINE SPEC.md`](./REELS%20PIPELINE%20SPEC.md) for the full product/technical spec.

---

## Quick Start

For macOS on Apple Silicon. Full detail for each step is in the sections below.

```bash
# 1. Install Python deps (creates .venv)
uv sync

# 2. Build ffmpeg-with-libass into ./vendor (one-time, ~10–15 min — see "FFmpeg with libass")
#    Homebrew's ffmpeg does NOT include libass, which the caption/brand stages need.

# 3. Add your LLM key (only transcript TEXT is ever sent off-machine)
cp .env.example .env        # then edit .env and paste your key

# 4. Verify everything is wired up — do this FIRST, it fails fast with fixes
uv run reels doctor

# 5. Drop one or more source videos into ./input, then run the whole pipeline
uv run reels run --config config.yaml

# → finished reels land in ./output as {source}__NN__{slug}.mp4 (+ reels.json / reels.md)
```

Prefer a browser UI? Jump to [Reels Studio](#web-app--reels-studio).

---

## Pipeline

```
ingest → transcribe → select (LLM) → plan-layout → cut → reframe → caption → brand → package
```

Each stage reads a per-video JSON manifest, does its work, writes outputs, and updates the manifest.
Any stage can be resumed with `--from <stage>` (and stopped early with `--to <stage>`).

## Architecture

The codebase follows **Clean Architecture / DDD** layering (dependencies point inward):

```
src/reels/
  domain/          # Entities, Value Objects, domain services, ports (zero framework deps)
  application/     # Use cases (one per stage) + pipeline orchestrator
  infrastructure/  # Adapters: ffprobe, faster-whisper, OpenAI/Claude, OpenCV, libass, config, persistence
  presentation/    # Typer CLI + FastAPI web adapter + composition root (dependency wiring)
```

- Domain ports (`Transcriber`, `ClipSelector`, `PresenterDetector`, …) are defined inside the
  domain/application layers; infrastructure provides the implementations.
- The CLI/web layer is the only composition root — it wires concrete adapters into use cases.

## Requirements

- **macOS on Apple Silicon** (Intel falls back to CPU with a logged slowdown warning).
- **Python 3.12** (managed via [`uv`](https://docs.astral.sh/uv/)) — install uv with `brew install uv`.
- **FFmpeg with libass** for subtitle burn-in (see the next section — Homebrew's build won't do).
- **An LLM API key** for the clip-selection stage (DeepSeek by default — see [Selection provider](#selection-provider-clip-selection-stage)).

The repo ships the brand **assets** it needs — `assets/outro.mp4`, `assets/Riser.wav`, and the
Arabic fonts under `assets/fonts/` are committed. Intro clip and logo are optional and `null` by
default in `config.yaml`.

## FFmpeg with libass

The caption and brand stages burn Arabic subtitles in via **libass**. Homebrew's `ffmpeg` ships
**without** libass, and neither the core nor the `homebrew-ffmpeg` tap exposes a `--with-libass`
option anymore — so you compile one from source (once, ≈10–15 min). Ingest/transcribe/cut/reframe
work without it; the CLI checks libass at startup and fails fast (with remediation) only when a stage
that needs it runs. `reels doctor` shows the status.

```bash
# 1. Install the codec/text libraries ffmpeg links against
brew install pkg-config x264 libass freetype fontconfig fribidi harfbuzz

# 2. Fetch the ffmpeg source (vendor/ is gitignored, so this stays local)
git clone --depth 1 --branch n7.1.1 https://github.com/FFmpeg/FFmpeg.git vendor/src
cd vendor/src

# 3. Configure it to install under ./vendor/ffmpeg with libass enabled
./configure \
  --prefix="$(cd ../.. && pwd)/vendor/ffmpeg" \
  --enable-gpl --enable-version3 \
  --enable-libx264 --enable-libass --enable-libfreetype \
  --enable-libfontconfig --enable-libfribidi --enable-libharfbuzz \
  --enable-videotoolbox --enable-audiotoolbox \
  --disable-doc --disable-debug \
  --extra-cflags=-I/opt/homebrew/include \
  --extra-ldflags=-L/opt/homebrew/lib

# 4. Build and install into ./vendor/ffmpeg
make -j"$(sysctl -n hw.ncpu)" && make install
cd ../..

# 5. Confirm libass is baked in
./vendor/ffmpeg/bin/ffmpeg -version | grep libass
```

`config.yaml` already points `paths.ffmpeg` at `vendor/ffmpeg/bin/ffmpeg`. Run `uv run reels doctor`
to confirm the **ffmpeg libass** check reads `ok`.

## Setup

```bash
uv sync                       # creates .venv and installs everything

# Provide your LLM key via a .env file (only transcript TEXT is ever sent):
cp .env.example .env          # then edit .env and fill in your key

uv run reels doctor           # verify config, ffmpeg+libass, key, fonts, input dir
```

`reels doctor` is the fastest way to catch a broken setup — run it before your first pipeline.

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

> 💸 **Cost note:** the select stage sends transcript **text** (not video) to a paid LLM API. Cost
> scales with transcript length — a full course video is typically a few cents per run. Nothing else
> in the pipeline makes network calls.

## Input

Drop your source videos into the **`input/`** folder (configurable via `paths.input_dir` in
`config.yaml`). `reels run` processes every video it finds there. Common container formats read by
ffmpeg work — `.mov`, `.mp4`, `.mkv`. Source videos are gitignored, so they're never committed.

```bash
cp ~/Downloads/"Lecture 1.mov" input/
uv run reels run
```

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

# Verbose per-stage logging:
uv run reels run -v

# Inspect environment / dependency health:
uv run reels doctor
```

Stages, in order, for `--from` / `--to`:
`ingest · transcribe · select · plan-layout · cut · reframe · caption · brand · package`.

Configuration lives in [`config.yaml`](./config.yaml) (see spec §7). Secrets are env-vars only.

## Output

Finished reels and their manifests land in the **`output/`** folder (`paths.output_dir`), grouped per
source video:

- `{source}__NN__{slug}.mp4` — one file per reel (e.g. `Lecture-1__03__domain-coupling.mp4`).
- `reels.json` — machine-readable manifest of every reel (spans, hook, captions, metadata).
- `reels.md` — a human-readable index of the reels.

Intermediate artefacts (transcripts, cut clips, per-stage state) live in `work/` (`paths.work_dir`)
and can be safely deleted to force a clean re-run. `output/`, `work/`, and `input/` are all gitignored.

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

Bind elsewhere with `reels web --host 0.0.0.0 --port 9000` (and `--config <path>` like the CLI).

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

## Troubleshooting

Run `uv run reels doctor` first — it flags most of these directly.

| Symptom | Cause & fix |
|---|---|
| Caption/brand stage errors with a libass message | You're on a libass-less ffmpeg. Build one from source (see [FFmpeg with libass](#ffmpeg-with-libass)) and confirm `paths.ffmpeg` points at `vendor/ffmpeg/bin/ffmpeg`. |
| `doctor` shows the selection key missing | `cp .env.example .env` and paste the key for your `selection.provider` (e.g. `DEEPSEEK_API_KEY`). |
| `reels run` finds no videos | Put at least one `.mov`/`.mp4`/`.mkv` in `input/` (or your `paths.input_dir`). |
| Transcription is very slow | On Intel Macs it falls back to CPU (logged). Lower `transcription.model_size` (e.g. `medium`) to trade accuracy for speed. |
| Want to re-run cleanly | Delete the relevant `work/` state, or use `--from <stage>` to redo from a point. |

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
