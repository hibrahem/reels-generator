"""Video library + detail endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from reels.application.queries.video_queries import ListVideos
from reels.presentation.api.schemas import VideoDetailOut, VideoSummaryOut
from reels.presentation.api.state import AppState, get_state

router = APIRouter()

StateDep = Annotated[AppState, Depends(get_state)]


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
