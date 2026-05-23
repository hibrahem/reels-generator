# Reels Studio — Web App Spec

A local, browser-based control center for the reels pipeline. It wraps the existing CLI/pipeline
in a friendly UI: manage configuration, ingest videos, run and monitor each stage live, review the
LLM-selected reels **on the original video player**, process reels individually or in bulk, and
manage the finished output.

> This is the build spec for the web layer. The pipeline itself (Slices 1–5) is done and unchanged.
> The web app is a **new delivery mechanism** (presentation adapter) over the same domain/
> application/infrastructure — no business logic moves into the web tier.

---

## 1. Goals & non-goals

### Goals
- One screen to drive everything: pick a video → see transcript → see selected reels → process →
  watch results, with live per-stage progress.
- Visualize reels **on the source timeline**: click a reel marker to play that exact span in the
  original video; see its hook/caption/confidence/mode.
- Edit before rendering: trim a reel's start/end ("split"), tweak title/hook/caption, drop a reel.
- Process granularity: run one reel now, run all, or resume from any stage — per video.
- Full config editing through a validated form (no YAML hand-editing required).
- Environment health at a glance (ffmpeg/libass, font, provider key) via the existing `doctor`.

### Non-goals (v1)
- No authentication / multi-user (local, single-user, localhost only).
- No cloud anything; secrets (API keys) stay in `.env` and are never shown or editable in the UI.
- No publishing to social platforms.
- No editing of the rendered video beyond re-running stages with changed config/trims.

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────┐
│ Frontend SPA (React + TS, Vite)  ── REST + SSE ──┐           │
└──────────────────────────────────────────────────┼──────────┘
                                                    ▼
┌────────────────────────────────────────────────────────────┐
│ Presentation: FastAPI app (src/reels/presentation/api/)      │
│  - thin handlers; build Container; invoke use cases          │
│  - JobManager: runs pipeline in background, streams progress │
├────────────────────────────────────────────────────────────┤
│ Application (unchanged): use cases + PipelineOrchestrator     │
│ Domain (unchanged) · Infrastructure (unchanged)              │
└────────────────────────────────────────────────────────────┘
```

- The FastAPI app reuses `Container.from_config(config.yaml)` and the existing use cases. Handlers
  contain **no business logic** — they translate HTTP ↔ use-case calls (Dependency Rule preserved).
- Long-running work (transcribe, batch render) runs as **Jobs** in a background thread/executor; the
  orchestrator's `on_progress` callback feeds a per-job event stream (SSE). One active job per video
  (a per-video lock); other videos can run concurrently within a worker limit.
- Dev: Vite dev server proxies `/api` → FastAPI. Prod/local: FastAPI serves the built SPA (`web/dist`)
  so it's a single `uv run reels web` process.

---

## 3. Backend API (FastAPI)

### Config & environment
- `GET /api/config` → current validated config + JSON schema (drives the form).
- `PUT /api/config` → validate (pydantic) and write `config.yaml`; 422 on invalid.
- `GET /api/doctor` → env health (ffmpeg path/version, libass, videotoolbox, font exists, input dir,
  selection provider/model, API-key presence).

### Video library
- `GET /api/videos` → list: `{id, filename, duration, resolution, fps, has_audio, stages_completed,
  reel_count, warnings}`.
- `POST /api/videos/scan` → ingest (probe new files in input dir); returns updated list.
- `POST /api/videos/upload` (optional) → copy an uploaded file into the input dir, then ingest.
- `GET /api/videos/{id}` → full manifest (metadata, transcript availability, reels w/ per-stage status).
- `GET /api/videos/{id}/transcript` → transcript JSON (segments + words).
- `GET /api/videos/{id}/media` → stream the **original** video (HTTP range) for the player.

### Pipeline jobs
- `POST /api/videos/{id}/run` → `{from_stage, to_stage, reel_indices?}` → starts a Job → `{job_id}`.
- `GET /api/jobs/{job_id}` → `{state, current_stage, per_stage_status, progress, warnings, error?}`.
- `GET /api/jobs/{job_id}/events` → **SSE** stream of `PipelineProgress` events + completion.
- `POST /api/jobs/{job_id}/cancel` (best-effort).
- `GET /api/jobs?video_id=` → active/recent jobs.

### Reels
- `GET /api/videos/{id}/reels` → `[{index, start, end, title, hook, caption, reason, confidence,
  visual_dependent, mode, stage_status, output_filename?}]`.
- `POST /api/videos/{id}/reels/{index}/run` → process one reel (plan-layout→package) as a Job.
- `PATCH /api/videos/{id}/reels/{index}` → edit `{start?, end?, title?, hook?, caption?}` (trim/split,
  re-snapped to word boundaries; clears that reel's downstream artifacts).
- `DELETE /api/videos/{id}/reels/{index}` → remove a reel from the manifest.
- `GET /api/videos/{id}/reels/{index}/media` → stream the finished reel.
- `GET /api/videos/{id}/sidecar` → `reels.json` + rendered `reels.md`.

All endpoints operate via use cases + the manifest repository; the API never touches ffmpeg directly.

---

## 4. Frontend

**Stack:** Vite + React + TypeScript, Tailwind CSS + shadcn/ui, TanStack Query (server state),
Zustand (local UI state), a video player (HTML5 `<video>` + a custom timeline overlay for reel
markers; upgrade to Vidstack if needed). RTL-aware (the captions/text are Arabic).

### 4.1 Library (dashboard)
- Grid of video cards: thumbnail, filename, duration, stage badges (ingest…package), reel count,
  warning count. Actions: **Scan input**, **Upload**, open detail.
- Empty state guiding the user to drop a video in `input/` or upload.

### 4.2 Video Detail — the core screen
- **Player (left/top):** original video with a custom timeline that renders each reel as a colored
  region. Click a region → seek to its start and play; "loop within reel" toggle. Hovering a region
  shows its title/hook. Current-time marker.
- **Reels panel (right):** cards per reel — title, confidence, duration, mode, hook, caption, and
  per-stage status chips (layout/cut/reframe/caption/brand/package). Per-card actions:
  **Play span**, **Process this reel**, **Re-run stage**, **Edit** (trim start/end via draggable
  handles on the timeline; edit hook/caption), **Preview finished**, **Delete**.
- **Pipeline bar:** from/to stage selectors, **Run** (whole video), **Process all reels**, **Resume**;
  live progress (SSE) with a bar per stage and a warnings/logs drawer.
- **Transcript tab:** scrollable transcript; clicking a word seeks the player; current word highlights
  as it plays.

### 4.3 Config editor
- Form generated from the config JSON schema, grouped by section (paths, transcription, selection,
  layout, captions, brand, output). Inline validation, helpful descriptions, save. Live caption-style
  preview where feasible. A **Doctor** panel shows environment health and the selected provider/key
  status (presence only — never the secret).

### 4.4 Finished reels gallery
- Grid of finished reels (vertical players), each with metadata (source span, hook, caption, mode,
  confidence) and a download button; link to the per-source `reels.md`.

### UX principles
- Live, non-blocking: jobs run in the background; the user can navigate while a render proceeds.
- Clear state everywhere: pending / running / done / failed / warning, with the manifest as truth.
- Confirmations for destructive actions (delete reel, overwrite output).
- Friendly defaults, tooltips, and empty states; RTL rendering for Arabic text.

---

## 5. Build slices (stop at each for review)

1. **API skeleton + Library + Doctor.** FastAPI app, `uv run reels web`, serve SPA shell; list
   videos, scan/ingest, doctor panel. **Checkpoint:** see the library + env health in the browser.
2. **Video Detail (read-only) + original player + transcript.** Manifest, reels list, stream original
   video, transcript viewer. **Checkpoint:** browse a video's reels + transcript.
3. **Jobs + run + live progress (SSE).** Run stages from the UI with per-stage progress + warnings.
   **Checkpoint:** trigger transcribe/select and watch progress.
4. **Timeline reel-markers + click-to-play span + finished-reel preview.** **Checkpoint:** click a
   reel on the source timeline and watch the finished reel.
5. **Config editor form.** Edit/save all config from the UI. **Checkpoint:** change a caption setting
   and re-render from the UI.
6. **Reel editing + per-reel/bulk processing + finished gallery.** Trim/split, edit hook/caption,
   process one/all, gallery. **Checkpoint:** end-to-end from the browser.
7. **Polish:** thumbnails, errors, empty states, responsiveness.

---

## 6. Dependencies & layout

- Backend (new optional dep group `web`): `fastapi`, `uvicorn[standard]`, `sse-starlette`,
  `python-multipart` (uploads). Reuses existing pydantic/config.
- Frontend in `web/` (Vite project): React, TS, Tailwind, shadcn/ui, @tanstack/react-query, zustand.
- New code: `src/reels/presentation/api/` (FastAPI app, routers, schemas, JobManager). CLI gains a
  `reels web` command to launch it.

---

## 7. Risks
1. **Long-running jobs + progress** — needs careful background execution + SSE; one job per video lock.
2. **Original-video streaming** — large files; must support HTTP range requests.
3. **Reel trim/split re-snapping** — editing a reel's span must re-snap to word boundaries and
   invalidate that reel's downstream artifacts so stages re-run cleanly.
4. **State source of truth** — the manifest stays authoritative; the UI reflects it, never forks it.
