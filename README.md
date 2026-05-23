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

  > ⚠️ The current Homebrew `ffmpeg` formula no longer bundles libass. A libass-enabled build is
  > required for the **caption** and **brand** stages (it is *not* needed for ingest/transcribe).
  > Install a full build, e.g. via the community tap:
  >
  > ```bash
  > brew tap homebrew-ffmpeg/ffmpeg
  > brew install homebrew-ffmpeg/ffmpeg/ffmpeg --with-libass --with-fontconfig --with-freetype --with-fribidi
  > ```
  >
  > The CLI checks libass capability at startup and fails fast (with this remediation) only when a
  > stage that needs it actually runs.

## Setup

```bash
uv sync                       # creates .venv and installs everything

# Provide your LLM key (only transcript text is sent):
export OPENAI_API_KEY=sk-...        # default provider
# or: export ANTHROPIC_API_KEY=sk-ant-...   (set selection.provider: claude in config.yaml)
```

## Usage

```bash
# Run the whole pipeline over the input folder:
uv run reels run --config config.yaml

# Resume from a specific stage (re-uses prior stage outputs from the manifest):
uv run reels run --from select --config config.yaml

# Inspect environment / dependency health:
uv run reels doctor

# Slice 1 (current): ingest + transcribe a single video and print the transcript path:
uv run reels run --from ingest --only transcribe --config config.yaml
```

Configuration lives in [`config.yaml`](./config.yaml) (see spec §7). Secrets are env-vars only.

## Build status

Built in thin slices per spec §10, stopping at each human checkpoint:

- [x] **Slice 1** — Skeleton + ingest + transcribe (word-level transcript JSON).
- [ ] Slice 2 — Select (LLM clip selection, validated).
- [ ] Slice 3 — Cut + MODE A reframe.
- [ ] Slice 4 — Arabic captions (the gate).
- [ ] Slice 5 — Brand + package.
- [ ] Slice 6 — Loop over clips.
- [ ] Slice 7 — Loop over folder.
- [ ] Slice 8 — MODE B (stacked slides + presenter).
