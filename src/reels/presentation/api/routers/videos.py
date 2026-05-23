"""Video library + detail endpoints."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from reels.application.queries.video_queries import ListVideos
from reels.application.use_cases.reel_editing import DeleteReel, EditReel, ReelNotFound
from reels.presentation.api.schemas import VideoDetailOut, VideoSummaryOut
from reels.presentation.api.state import AppState, get_state

router = APIRouter()

StateDep = Annotated[AppState, Depends(get_state)]


def _video_mime(suffix: str) -> str:
    return {".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska"}.get(
        suffix.lower(), "video/mp4"
    )


@router.get("/videos", response_model=list[VideoSummaryOut])
def list_videos(state: StateDep) -> list[VideoSummaryOut]:
    c = state.container
    summaries = ListVideos(library=c.library, manifests=c.manifests).execute()
    return [VideoSummaryOut.of(s) for s in summaries]


@router.post("/videos/scan", response_model=list[VideoSummaryOut])
def scan_videos(state: StateDep) -> list[VideoSummaryOut]:
    c = state.container
    c.orchestrator.ingest.execute()  # probe + create/update manifests for input-dir videos
    summaries = ListVideos(library=c.library, manifests=c.manifests).execute()
    return [VideoSummaryOut.of(s) for s in summaries]


@router.get("/videos/{video_id}", response_model=VideoDetailOut)
def get_video(video_id: str, state: StateDep) -> VideoDetailOut:
    c = state.container
    manifest = c.manifests.load(video_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"video '{video_id}' not found (not ingested?)")
    return VideoDetailOut.of(manifest, c.settings.paths.output_dir)


class ReelEdit(BaseModel):
    start: float | None = None
    end: float | None = None
    title: str | None = None
    hook: str | None = None
    caption: str | None = None


@router.patch("/videos/{video_id}/reels/{index}", response_model=VideoDetailOut)
def edit_reel(video_id: str, index: int, edit: ReelEdit, state: StateDep) -> VideoDetailOut:
    c = state.container
    manifest = c.manifests.load(video_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="video not found")
    try:
        EditReel(manifests=c.manifests, transcripts=c.transcripts).execute(
            manifest, index, start=edit.start, end=edit.end, title=edit.title,
            hook=edit.hook, caption=edit.caption,
        )
    except ReelNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VideoDetailOut.of(manifest, c.settings.paths.output_dir)


@router.delete("/videos/{video_id}/reels/{index}", response_model=VideoDetailOut)
def delete_reel(video_id: str, index: int, state: StateDep) -> VideoDetailOut:
    c = state.container
    manifest = c.manifests.load(video_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="video not found")
    try:
        DeleteReel(manifests=c.manifests).execute(manifest, index)
    except ReelNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return VideoDetailOut.of(manifest, c.settings.paths.output_dir)


@router.get("/videos/{video_id}/transcript")
def get_transcript(video_id: str, state: StateDep) -> dict[str, Any]:
    manifest = state.container.manifests.load(video_id)
    if manifest is None or manifest.transcript_path is None:
        raise HTTPException(status_code=404, detail="transcript not available — run transcribe")
    return json.loads(manifest.transcript_path.read_text(encoding="utf-8"))


@router.get("/videos/{video_id}/media")
def get_media(video_id: str, state: StateDep) -> FileResponse:
    manifest = state.container.manifests.load(video_id)
    if manifest is None or not manifest.source.path.exists():
        raise HTTPException(status_code=404, detail="source video not found")
    # Prefer the browser-friendly preview proxy (H.264+AAC) if it's been generated.
    preview = manifest.source.working_dir / "preview.mp4"
    if preview.exists():
        return FileResponse(preview, media_type="video/mp4")
    # FileResponse honors the Range header (206), so the player can seek.
    return FileResponse(manifest.source.path, media_type=_video_mime(manifest.source.path.suffix))


@router.get("/videos/{video_id}/poster")
def get_poster(video_id: str, state: StateDep) -> FileResponse:
    c = state.container
    manifest = c.manifests.load(video_id)
    if manifest is None or not manifest.source.path.exists():
        raise HTTPException(status_code=404, detail="source video not found")
    poster = manifest.source.working_dir / "poster.jpg"
    if not poster.exists():
        from reels.infrastructure.ffmpeg.preview import build_poster

        meta = manifest.source.metadata
        at = (meta.duration_seconds / 2) if meta else 5.0
        ffmpeg_path = str(c.settings.paths.ffmpeg) if c.settings.paths.ffmpeg else None
        try:
            build_poster(manifest.source.path, poster, at, ffmpeg_path)
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return FileResponse(poster, media_type="image/jpeg")


@router.get("/videos/{video_id}/reels/{index}/media")
def get_reel_media(video_id: str, index: int, state: StateDep) -> FileResponse:
    c = state.container
    manifest = c.manifests.load(video_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="video not found")
    reel = next((r for r in manifest.reels if r.index == index), None)
    if reel is None:
        raise HTTPException(status_code=404, detail=f"reel {index} not found")
    output = c.settings.paths.output_dir / reel.output_filename()
    path = output if output.exists() else reel.final_path
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail=f"reel {index} not rendered yet")
    return FileResponse(path, media_type="video/mp4")
