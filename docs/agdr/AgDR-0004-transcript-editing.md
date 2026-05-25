# Transcript editing — word-level, timing-preserving

> In the context of letting creators correct misheard words so fixes flow into the burned-in captions without re-running transcription, facing the fact that the whole pipeline (caption karaoke / active-word highlighting, clip-boundary snapping) keys off per-word start/end, I decided to allow editing only each word's *text* while preserving every word's timestamp — exposed as a `PATCH /videos/{id}/transcript` that the save use case validates is structure- and timing-preserving — to achieve corrected captions with zero timing drift, accepting that re-segmentation, re-timing, and word insert/delete are explicitly out of scope.

## Context

A transcript is `Transcript → Segment[] → Word[]`, where each `Word` carries `text`, `start`, `end`, `probability` (`src/reels/domain/transcript/transcript.py`). Downstream stages depend on word timings: the caption stage renders active-word karaoke from per-word start/end, and `snap_*_to_word_boundary` uses them to align cuts. Whisper's Arabic word text is often wrong even when its timing is fine, so the high-value edit is "fix the text, keep the timing".

The transcript persists as `transcript.json` in the video's working dir (`JsonTranscriptRepository`); `GET /videos/{id}/transcript` already serves it. The same `TranscriptView` component renders the transcript on both VideoDetail (whole video) and ReelDetail (single reel, where it also drives cut selection via `selStart/selEnd/onSetStart/onSetEnd`).

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Word-level text edit, timings preserved (chosen)** | Captions stay perfectly aligned; smallest possible change surface; trivially safe — server rejects any timing/structure change; reuses existing JSON shape | Cannot fix segmentation or insert/delete words (acceptable — that's a re-transcribe concern) |
| Free-form segment-text edit (edit the joined segment string) | Simplest UI | Destroys the word→timing mapping; caption karaoke would have no per-word timings to highlight |
| Full re-transcribe-with-hints | Could fix everything | Heavyweight, slow, defeats the "without re-running transcription" requirement; non-deterministic |

## Decision

Chosen: **word-level text editing with preserved timings.**

- **Payload shape** — `PATCH /videos/{id}/transcript` body is the full edited segment list, mirroring the GET response so the client round-trips what it fetched:
  ```json
  { "segments": [
      { "text": "...", "start": 0.0, "end": 1.5,
        "words": [ { "text": "...", "start": 0.0, "end": 0.4, "probability": 0.99 }, ... ] }
  ] }
  ```
  Response is the persisted transcript JSON (same shape as GET).
- **Invariant lives in the application layer** — `EditTranscript` (`src/reels/application/use_cases/edit_transcript.py`) loads the existing transcript and asserts the edit preserves segment count, per-segment word count, and every segment/word `(start, end)`. Only `text` (word text + the convenience segment text) may change. A violation raises `TranscriptStructureChanged` → HTTP 422; a missing transcript raises `TranscriptNotAvailable` → 404. This keeps "preserve timings" a server-enforced rule rather than something trusted from the client.
- **Layering** — API boundary (`schemas.py` `TranscriptEditIn` → `to_domain_segments()`) validates/parses; the use case orchestrates domain + the persistence port; IO stays in `JsonTranscriptRepository` (unchanged — `save` already serialises words+timings). No ffmpeg/IO leaks into the use case.
- **Frontend** — the shared `TranscriptView` gains an opt-in `videoId` prop. When present it shows an "Edit transcript" toggle; in edit mode each word renders as an input (timing shown as a tooltip) and only its text mutates; Save calls `api.editTranscript` and invalidates `["transcript", id]`. Read-only rendering, RTL handling (`dir="rtl"`/`"auto"`), and ReelDetail's seek/selection props are untouched and disabled while editing so they don't conflict.

## Consequences

- Captions consume edited words on the **next caption render** — editing rewrites `transcript.json`; re-running the caption stage picks up the corrected text with identical timings, so karaoke highlighting is unaffected.
- Editing does **not** invalidate existing renders (unlike a reel span edit) because timings are unchanged; the corrected text only matters when captions are (re)rendered.
- Segmentation / timing / insert-delete edits are intentionally rejected (422). If a creator needs those, the path is re-transcribe — a future, separate concern.
- A segment with no word-level timings shows a disabled fallback input (can't safely edit text we can't map to timings).

## Artifacts

- Ticket: hibrahem/reels-generator#20
- Backend: `src/reels/application/use_cases/edit_transcript.py`, `src/reels/presentation/api/routers/videos.py`, `src/reels/presentation/api/schemas.py`
- Tests: `tests/application/test_edit_transcript.py`
- Frontend: `web/src/components/TranscriptView.tsx`, `web/src/lib/api.ts`, `web/src/components/VideoDetail.tsx`, `web/src/components/ReelDetail.tsx`
