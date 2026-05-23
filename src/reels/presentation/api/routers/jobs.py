"""Pipeline-job endpoints: start runs, query status, and stream live progress (SSE)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from reels.application.pipeline_stage import Stage
from reels.application.run_options import RunOptions
from reels.presentation.api.jobs import Job, JobManager, Reporter
from reels.presentation.api.state import AppState, get_state

router = APIRouter()

StateDep = Annotated[AppState, Depends(get_state)]


def get_jobs(request: Request) -> JobManager:
    return request.app.state.reels.jobs


JobsDep = Annotated[JobManager, Depends(get_jobs)]


class RunRequest(BaseModel):
    from_stage: str = "ingest"
    to_stage: str = "package"
    reel_indices: list[int] | None = None


def _parse_stage(value: str) -> Stage:
    try:
        return Stage(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"unknown stage '{value}'") from exc


def _pipeline_runner(state: AppState, video_id: str, req: RunRequest):
    from_stage = _parse_stage(req.from_stage)
    to_stage = _parse_stage(req.to_stage)
    options = RunOptions(
        reel_indices=frozenset(req.reel_indices) if req.reel_indices else None
    )

    def runner(reporter: Reporter) -> None:
        container = state.container
        container.orchestrator.run(
            from_stage=from_stage,
            to_stage=to_stage,
            on_progress=lambda p: reporter.emit(p.stage.value, p.source_id, p.message),
            options=options,
            video_ids={video_id},
        )

    return runner


def _job_dict(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "kind": job.kind,
        "video_id": job.video_id,
        "from_stage": job.from_stage,
        "to_stage": job.to_stage,
        "reel_indices": job.reel_indices,
        "state": job.state,
        "error": job.error,
        "events": [dataclasses.asdict(e) for e in job.events()],
    }


@router.post("/videos/{video_id}/run")
def run_pipeline(video_id: str, req: RunRequest, state: StateDep, jobs: JobsDep) -> dict[str, str]:
    if state.container.manifests.load(video_id) is None and req.from_stage != "ingest":
        raise HTTPException(status_code=404, detail="video not found — ingest first")
    job = jobs.submit(
        kind="pipeline",
        video_id=video_id,
        runner=_pipeline_runner(state, video_id, req),
        from_stage=req.from_stage,
        to_stage=req.to_stage,
        reel_indices=req.reel_indices,
    )
    return {"job_id": job.id}


@router.post("/videos/{video_id}/reels/{index}/run")
def run_reel(video_id: str, index: int, state: StateDep, jobs: JobsDep) -> dict[str, str]:
    req = RunRequest(from_stage="plan-layout", to_stage="package", reel_indices=[index])
    job = jobs.submit(
        kind="reel",
        video_id=video_id,
        runner=_pipeline_runner(state, video_id, req),
        from_stage=req.from_stage,
        to_stage=req.to_stage,
        reel_indices=[index],
    )
    return {"job_id": job.id}


@router.post("/videos/{video_id}/preview")
def make_preview(video_id: str, state: StateDep, jobs: JobsDep) -> dict[str, str]:
    container = state.container
    manifest = container.manifests.load(video_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail="video not found")
    src = manifest.source.path
    out = manifest.source.working_dir / "preview.mp4"
    ffmpeg_path = str(container.settings.paths.ffmpeg) if container.settings.paths.ffmpeg else None

    def runner(reporter: Reporter) -> None:
        from reels.infrastructure.ffmpeg.preview import build_preview

        build_preview(
            src, out, ffmpeg_path, on_progress=lambda m: reporter.emit("preview", video_id, m)
        )
        reporter.emit("preview", video_id, "done")

    job = jobs.submit(kind="preview", video_id=video_id, runner=runner)
    return {"job_id": job.id}


@router.get("/jobs/{job_id}")
def get_job(job_id: str, jobs: JobsDep) -> dict[str, Any]:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_dict(job)


@router.get("/jobs")
def list_jobs(jobs: JobsDep, video_id: str | None = None) -> list[dict[str, Any]]:
    return [_job_dict(j) for j in jobs.list(video_id)]


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, jobs: JobsDep) -> EventSourceResponse:
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    async def stream():
        sent = 0
        while True:
            events = job.events()
            while sent < len(events):
                e = events[sent]
                sent += 1
                yield {"event": "progress", "data": json.dumps(dataclasses.asdict(e))}
            if job.state in ("done", "failed") and sent >= len(job.events()):
                yield {"event": "end", "data": json.dumps({"state": job.state, "error": job.error})}
                return
            await asyncio.sleep(0.25)

    return EventSourceResponse(stream())
