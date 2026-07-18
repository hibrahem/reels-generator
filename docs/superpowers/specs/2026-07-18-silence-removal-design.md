# Silence Remover — Design

**Date:** 2026-07-18
**Status:** Approved

## Overview

A standalone tool in Reels Studio (the FastAPI + React web app) that takes an uploaded
video and produces a copy with all silent passages removed. It is completely independent
of the reels pipeline: no manifest, no stages, no per-reel state.

**Workflow:** upload video → adjust up to three settings → process (one click) → download
the trimmed result with before/after duration stats.

## Approach

ffmpeg-only (no new dependencies):

1. Detect silence intervals with `ffmpeg -af silencedetect`.
2. Compute the complementary *keep* segments in a pure domain service.
3. Render the output with a single trim + concat filter pass, re-encoded to H.264/AAC mp4.

Alternatives considered and rejected:

- **auto-editor wrapper** — less code but a new external dependency, less control over
  progress reporting and behavior.
- **VAD model** — better for noisy audio (detects speech rather than loudness) but adds a
  model dependency and complexity the one-click use case does not need.

## Architecture

### Domain layer — `src/reels/domain/silence_removal/`

- `SilenceInterval` — value object: `start`/`end` in seconds, immutable, validates
  `0 <= start < end`.
- `KeepSegment` — value object: a span of the source video to retain.
- Pure domain service `compute_keep_segments(silences, video_duration, min_silence, padding)`:
  - Ignores silences shorter than `min_silence`.
  - Shrinks each cut by `padding` seconds on both sides so speech is not clipped.
  - Merges adjacent/overlapping keep segments and clamps to `[0, video_duration]`.
  - Raises a domain error if the result is empty (fully silent input).
  - No framework dependencies; fully unit-testable without mocks.

### Application layer — `src/reels/application/`

- Ports (interfaces):
  - `SilenceDetector.detect(video_path, threshold_db, min_silence) -> list[SilenceInterval]`
  - `SegmentCutter.cut(video_path, segments, output_path) -> None`
- Use case `RemoveSilence`:
  - Orchestrates detect → compute keep segments → cut.
  - Returns a result DTO: original duration, output duration, number of cuts removed.
  - Contains no business logic (segment math lives in the domain service).

### Infrastructure layer — `src/reels/infrastructure/ffmpeg/`

- `FfmpegSilenceDetector` — runs `ffmpeg -af silencedetect=noise=<db>dB:d=<dur>`,
  parses `silence_start` / `silence_end` lines from stderr.
- `FfmpegSegmentCutter` — builds a single `filter_complex` trim/atrim + concat graph,
  re-encodes to H.264 video + AAC audio in an mp4 container.

### Presentation layer

- **API** — new router `src/reels/presentation/api/routers/silence.py`:
  - `POST` upload-and-process endpoint: accepts the video file and the three settings,
    creates a job on the existing background-job manager (new job kind), returns a job id.
    Progress is reported through the existing SSE event mechanism.
  - `GET` download endpoint for the finished output file.
  - Uploaded and output files live in a tool-specific working directory, not in the
    reels pipeline workspace.
- **Web** — new page/tab "Silence Remover" in `web/src/`:
  - File upload, three settings with defaults, process button, progress display,
    download button with original vs. trimmed duration and cut count.

## Settings and defaults

| Setting | Default | Meaning |
|---|---|---|
| Silence threshold | −35 dB | Audio below this level counts as silence |
| Min silence duration | 0.6 s | Shorter quiet gaps are left alone |
| Edge padding | 0.15 s | Audio kept on each side of a cut |

## Error handling

- **No audio track** → clear error before any processing ("this video has no audio").
- **No silence detected** → succeed with zero cuts; UI notes the output equals the input.
- **Fully silent input** → domain error surfaced as a friendly failure message.
- ffmpeg failures → job fails with the stderr tail in the job error.

## Testing

- **Domain (no mocks):** segment math — padding applied, short silences ignored,
  silences at file start/end, overlapping/adjacent merges, fully-silent rejection.
- **Infrastructure:** silencedetect stderr parser tested against captured ffmpeg output.
- **API:** happy-path test for upload → job → download using a small fixture video.
