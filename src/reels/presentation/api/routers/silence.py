"""Silence Remover tool endpoints — standalone from the reels pipeline.

Uploads and outputs live under work_dir/tools/silence/<token>/, keyed by a job token.
Progress streams through the existing job SSE endpoint (GET /api/jobs/{job_id}/events).
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from reels.application.use_cases.remove_silence import SilenceRemovalSettings
from reels.infrastructure.ffmpeg.ffprobe_video_prober import FFprobeError, FFprobeVideoProber
from reels.presentation.api.jobs import Reporter
from reels.presentation.api.state import AppState, get_state

router = APIRouter()

StateDep = Annotated[AppState, Depends(get_state)]

_ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def _tool_dir(state: AppState, token: str) -> Path:
    if not token.isalnum():  # tokens are hex; also guards path traversal
        raise HTTPException(status_code=404, detail="unknown token")
    return state.container.settings.paths.work_dir / "tools" / "silence" / token


@router.post("/silence/jobs")
def start_silence_job(
    state: StateDep,
    file: Annotated[UploadFile, File()],
    threshold_db: Annotated[float, Form()] = -35.0,
    min_silence: Annotated[float, Form()] = 0.6,
    padding: Annotated[float, Form()] = 0.15,
) -> dict[str, str]:
    original = Path(file.filename or "input.mp4")
    suffix = original.suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=422, detail=f"unsupported file type '{suffix}'")

    token = uuid.uuid4().hex[:12]
    workdir = _tool_dir(state, token)
    workdir.mkdir(parents=True, exist_ok=True)
    in_path = workdir / f"input{suffix}"
    with in_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    # Fail fast, before any processing, on files we can't handle (spec: error handling).
    try:
        meta = FFprobeVideoProber().probe(in_path)
    except FFprobeError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"could not read video: {exc}") from exc
    if not meta.has_audio:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=422, detail="this video has no audio track")

    out_path = workdir / f"{original.stem}.nosilence.mp4"
    settings = SilenceRemovalSettings(
        threshold_db=threshold_db, min_silence=min_silence, padding=padding
    )
    remover = state.container.silence_remover

    def runner(reporter: Reporter) -> None:
        result = remover.execute(
            in_path,
            out_path,
            settings,
            on_progress=lambda stage, message: reporter.emit(stage, token, message),
        )
        (workdir / "result.json").write_text(
            json.dumps(
                {
                    "original_duration": result.original_duration,
                    "output_duration": result.output_duration,
                    "cuts_removed": result.cuts_removed,
                    "output_filename": out_path.name,
                }
            ),
            encoding="utf-8",
        )
        reporter.emit("done", token, "silence removal complete")

    job = state.jobs.submit(kind="silence", video_id=token, runner=runner)
    return {"job_id": job.id, "token": token}


@router.get("/silence/jobs/{token}/result")
def silence_result(token: str, state: StateDep) -> dict[str, Any]:
    path = _tool_dir(state, token) / "result.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="result not ready")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/silence/jobs/{token}/download")
def silence_download(token: str, state: StateDep) -> FileResponse:
    workdir = _tool_dir(state, token)
    result = workdir / "result.json"
    if not result.exists():
        raise HTTPException(status_code=404, detail="output not ready")
    name = json.loads(result.read_text(encoding="utf-8"))["output_filename"]
    out = workdir / name
    if not out.exists():
        raise HTTPException(status_code=404, detail="output file missing")
    return FileResponse(out, media_type="video/mp4", filename=name)
