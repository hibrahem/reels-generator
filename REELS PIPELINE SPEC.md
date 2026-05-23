# Reels Pipeline — Product & Technical Spec

A local-first CLI that turns long-form Arabic course videos into a series of vertical (9:16) social reels. The tool transcribes each source video, uses an LLM to select self-contained teaching moments, then cuts, reframes, captions, and brands each clip. No cloud video processing. No auto-publishing in v1.

This document is the build spec for Claude Code. Read it top to bottom before writing code. Build in the slices described in Section 10, and stop at each checkpoint for a human eyeball before continuing.

-----

## 1. Goals and non-goals

### Goals

- Take a folder of long course videos (15 min to 1 hour each) and produce a folder of finished, post-ready vertical reels.
- Let an LLM decide which segments become reels and how many per source, based on content rather than a fixed count.
- Handle the real layout of the source: presenter on the right, slides often (not always) on the left.
- Burn in correct, word-by-word Arabic captions with mixed-in English, rendered with proper Arabic shaping.
- Run fully local except for the LLM text call (transcript text only; no video ever leaves the machine).

### Non-goals (v1)

- No auto-publishing to any platform. Output is files on disk plus a metadata sidecar.
- No GUI. CLI only.
- No multi-speaker diarization. Single presenter assumed.
- No translation. Captions stay in the source language (Arabic + occasional English).

-----

## 2. Target environment

- **OS:** macOS on Apple Silicon (M-series). Transcription should use the Metal/MPS backend where available. (If run on an Intel Mac, fall back to CPU; flag the slowdown but do not block.)
- **Language:** Python 3.11+.
- **External binary:** FFmpeg (with libass support for subtitle burn-in). Document the `brew install ffmpeg` step; fail fast with a clear message if libass is missing.
- **LLM:** Pluggable provider, supporting both Anthropic (Claude) and OpenAI. Selectable via config/env. Only transcript text is sent.

-----

## 3. Input assumptions

- Source videos are mostly 16:9, typically 1920x1080. Do not hardcode resolution; read it per file with ffprobe.
- Audio is Arabic with occasional English words (code-switching). Right-to-left script.
- Layout per source: presenter occupies a region on the **right** side of the frame. Slides usually occupy the left, but not always; some stretches are presenter-only.
- The presenter region is **not** fixed across the series and may shift within a video. Position must be detected, not assumed (see Section 6).

-----

## 4. High-level pipeline

Each stage is an independent, separately testable step. State is passed via files on disk plus a per-video JSON manifest, so any stage can be re-run without redoing the ones before it.

```
ingest -> transcribe -> select (LLM) -> plan-layout -> cut -> reframe -> caption -> brand -> package
```

Linear orchestration in plain Python. Do **not** introduce a graph/state-machine framework in v1. Each stage reads the manifest, does its work, writes its outputs and updates the manifest. A `--from <stage>` flag lets a run resume at any stage.

-----

## 5. Stage detail

### 5.1 ingest

- Scan the input folder for video files. For each, run ffprobe and record duration, resolution, fps, audio stream info into the manifest.
- Create a per-video working directory under the output root.

### 5.2 transcribe

- Use a local Whisper implementation. **Preferred: `faster-whisper`** (CTranslate2; good MPS/CPU performance, lower memory). `whisperx` is acceptable if word-level alignment quality on Arabic proves better in testing.
- Produce **word-level timestamps**. The whole pipeline keys off these.
- Model size: default to `large-v3` for Arabic accuracy; expose as config. Note that smaller models degrade Arabic noticeably.
- Persist the raw transcript (words + timestamps + segments) as JSON in the working dir.
- **Known risk:** Arabic word-level timing is less reliable than English. Do not assume perfection. Downstream caption rendering must tolerate slight timing drift.

### 5.3 select (the LLM stage)

- Input: the full timestamped transcript (text + segment timings), plus video duration.
- Task: identify the self-contained teaching moments that work as standalone reels. **Number is content-driven, not fixed** — return as many as are genuinely good, zero is a valid answer for a weak source.
- Output: strict JSON array. Each item:
  - `start` (seconds, float)
  - `end` (seconds, float)
  - `title` (short internal label)
  - `hook` (on-screen hook text, in the source language)
  - `caption` (suggested post caption)
  - `reason` (why this stands alone / why it’ll land)
  - `confidence` (0-1)
- Constraints to enforce in the prompt AND validate in code after:
  - Each clip self-contained: makes sense without surrounding context.
  - Respect a min/max duration window (config; default 20-90s). Reject or flag clips outside it.
  - Clips must not overlap. If the LLM returns overlaps, reconcile (drop lower-confidence) and log.
  - `start`/`end` must fall within video duration and snap to nearest word boundary from the transcript.
- The LLM does **text only**. It never sees pixels and never decides crop geometry.
- Provider abstraction: a thin interface with `select_clips(transcript) -> list[Clip]`, implemented for Claude and OpenAI. Use structured/JSON output mode; strip code fences defensively before parsing; retry once on malformed JSON.

### 5.4 plan-layout

- For each selected clip, decide the **reframe mode**. Two modes:
  - **MODE A — presenter-only crop:** a 9:16 column anchored on the detected presenter region. Used when there is no meaningful slide content during the clip.
  - **MODE B — stacked:** slides (cropped from the left/main region) on top, presenter on the bottom, composited into 9:16. Used when slide content matters for that clip.
- How the decision is made:
  - The **LLM hints** whether the moment is visual/slide-dependent or talk-dependent (add a `visual_dependent` boolean to the select output). This is a hint, not the final call.
  - A **local vision pass** confirms presence/position. Run lightweight face detection (e.g. OpenCV Haar/DNN or `mediapipe`) on a few sampled frames across the clip to locate the presenter bounding box and its stability. This produces the actual crop geometry.
- Output per clip: chosen mode + concrete pixel crop rectangles, written to the manifest. No video written yet.
- **This is a genuinely tricky stage. Build MODE A end-to-end first and ship it before attempting MODE B.** A v1 that only does presenter-only crops is a valid, useful milestone.

### 5.5 cut

- Cut each selected clip from the source using FFmpeg and the snapped word-boundary timestamps.
- Prefer accurate (re-encode) cuts over fast stream-copy cuts to avoid keyframe drift at clip boundaries.

### 5.6 reframe

- Apply the geometry from plan-layout.
- MODE A example (right-anchored 9:16 column from a 1080p source, geometry comes from detection, not hardcoded):
  
  ```
  ffmpeg -i clip.mp4 -vf "crop=W:H:X:Y,scale=1080:1920" -c:a copy out.mp4
  ```
  
  where `crop=H*9/16:H:(detected_x):0` gives the column around the presenter.
- MODE B: crop slide region and presenter region separately, scale, and `vstack` (or overlay onto a 1080x1920 canvas with defined top/bottom zones). Keep the split ratio in config.

### 5.7 caption  — HIGHEST RISK, treat with care

- Generate word-by-word (“karaoke”) captions from the word-level timestamps.
- **Arabic correctness is the make-or-break requirement.** Naive burn-in mangles Arabic (disconnected letters, reversed order). Required handling:
  - Shape and order text with `arabic-reshaper` + `python-bidi` before it ever reaches the renderer.
  - Render via libass (`.ass` subtitles) through FFmpeg, using a font with full Arabic support (e.g. a Noto Arabic / Cairo / Amiri family). Bundle or document the font; do not rely on system defaults.
  - Mixed Arabic + English (bidi) must render in correct visual order. Test specifically with a code-switched line.
  - Word-by-word highlight: implement via per-word `.ass` events/timing. Keep styling in config (active-word color, base color, size, position, safe-margin from edges so platform UI doesn’t cover it).
- Build a **dedicated caption test harness** with a few hand-picked tricky lines (pure Arabic, Arabic+English, fast speech) and visually verify rendered frames before wiring captions into the batch path.

### 5.8 brand

- Prepend intro, append outro (assets provided by the user — wire as configurable paths).
- Overlay logo (configurable position/opacity/size).
- Ensure consistent output spec: 1080x1920, H.264, AAC, sensible bitrate, faststart.

### 5.9 package

- Write each finished reel to the output folder with a stable naming scheme: `{source_name}__{NN}__{slug}.mp4`.
- Write a sidecar `reels.json` (and a human-readable `reels.md`) per source containing, for each reel: filename, start/end in source, title, hook, post caption, mode used, confidence.

-----

## 6. The presenter-detection problem (call-out)

Because position is dynamic and slides are intermittent, crop geometry cannot be hardcoded. The approach:

1. Sample N frames across each clip (e.g. every 2s).
1. Run local face/person detection to get the presenter bounding box per sample.
1. If the box is stable and slides are absent/irrelevant -> MODE A around that box.
1. If slide content is present and flagged relevant -> MODE B.
1. If detection is unstable or fails -> fall back to a configurable default crop and **log a warning into the manifest** so the human can review that specific reel.

Detection runs locally (OpenCV or mediapipe). No cloud vision. This stage should degrade gracefully: a wrong-but-reviewable crop beats a crash.

-----

## 7. Configuration

Single `config.yaml` (or `.toml`), no settings buried in code. At minimum:

- paths: input dir, output dir, intro, outro, logo, font.
- transcription: model size, backend, language hint (`ar`).
- selection: provider (`claude`|`openai`), model name, min/max clip seconds, temperature.
- layout: MODE B split ratio, default fallback crop, detection sample interval.
- captions: font family, sizes, active/base colors, position, safe margins.
- output: resolution, bitrate, codecs.

Secrets (API keys) via environment variables, never in the config file.

-----

## 8. Project structure (suggested)

```
reels/
  cli.py                 # entrypoint, stage orchestration, --from flag
  config.py              # load + validate config
  manifest.py            # per-video manifest read/write
  stages/
    ingest.py
    transcribe.py
    select.py            # LLM provider interface + Claude/OpenAI impls
    layout.py            # detection + mode decision + geometry
    cut.py
    reframe.py
    caption.py           # arabic shaping + .ass generation + burn-in
    brand.py
    package.py
  llm/
    base.py              # select_clips interface
    claude.py
    openai.py
  detect/
    presenter.py         # face/person detection helpers
  tests/
    caption_harness/     # tricky Arabic/English lines + expected renders
config.yaml
README.md
```

-----

## 9. Dependencies

- `ffmpeg` (system, with libass) — hard requirement, check at startup.
- `faster-whisper` (or `whisperx`) for transcription.
- `opencv-python` or `mediapipe` for presenter detection.
- `arabic-reshaper`, `python-bidi` for caption text shaping.
- `anthropic` and `openai` SDKs for the selection stage.
- `pyyaml`/`tomli`, `pydantic` (config + manifest validation), `ffmpeg-python` or direct subprocess calls.

-----

## 10. Build order (thin slices — stop at each checkpoint)

Each slice ends at something inspectable. Do not jump ahead.

1. **Skeleton + ingest + transcribe.** Point at one real video, produce a word-level transcript JSON. **Checkpoint:** human eyeballs the transcript on Arabic content.
1. **Select.** Feed that transcript to the LLM, get validated JSON clips. **Checkpoint:** human checks the chosen segments against the transcript for sense and self-containment.
1. **Cut + MODE A reframe.** Produce one presenter-only vertical clip (no captions yet). **Checkpoint:** watch it — is the presenter framed correctly?
1. **Captions (Arabic).** Add word-by-word burn-in to that one clip via the caption harness. **Checkpoint:** verify Arabic shaping, bidi order, and code-switched English on rendered frames. This is the gate — do not proceed until captions are correct.
1. **Brand + package.** Intro/outro/logo + sidecar metadata for the single clip. **Checkpoint:** one fully finished reel.
1. **Loop over clips** within one video. **Checkpoint:** a full set of reels from one source.
1. **Loop over the folder** of videos. **Checkpoint:** batch run.
1. **MODE B (stacked slides+presenter).** Only after everything above is solid. **Checkpoint:** a slide-dependent reel that reads well vertically.

-----

## 11. Risks (ranked)

1. **Arabic word-by-word captions** (shaping, bidi, code-switching, timing drift). Highest risk. Dedicated harness; gate the build on it.
1. **Dynamic presenter detection + MODE B compositing.** Build MODE A first; MODE B is a later slice; always have a logged fallback crop.
1. **Arabic word-level timestamp accuracy from Whisper.** Mitigate with `large-v3`; tolerate drift in caption logic.
1. **LLM clip selection quality.** Mitigate with strict schema, overlap/duration validation, and the step-2 human checkpoint.
1. **Re-encode cost on 1-hour sources.** Accept for accuracy; consider a coarse scene/segment pre-filter later if speed becomes a problem.

-----

## 12. Definition of done (v1)

- One command turns a folder of course videos into a folder of finished 9:16 reels plus per-source `reels.json`/`reels.md`.
- MODE A (presenter-only) works reliably; MODE B works for clearly slide-dependent clips or degrades to a logged fallback.
- Arabic + English captions render correctly, word by word.
- Any stage can be re-run via `--from`.
- No video leaves the machine; only transcript text is sent to the LLM.