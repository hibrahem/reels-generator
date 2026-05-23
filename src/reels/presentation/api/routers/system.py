"""Config and environment-health endpoints."""

from __future__ import annotations

import os
from typing import Annotated, Any

import yaml
from fastapi import APIRouter, Depends, HTTPException

from reels.infrastructure.config.settings import Settings
from reels.presentation.api.schemas import DoctorCheck, DoctorOut
from reels.presentation.api.state import AppState, get_state

router = APIRouter()

StateDep = Annotated[AppState, Depends(get_state)]


@router.get("/config")
def get_config(state: StateDep) -> dict[str, Any]:
    settings = state.container.settings
    return {"config": settings.model_dump(mode="json"), "schema": Settings.model_json_schema()}


@router.put("/config")
def put_config(payload: dict[str, Any], state: StateDep) -> dict[str, Any]:
    config = payload.get("config", payload)
    try:
        validated = Settings.model_validate(config)
    except Exception as exc:  # noqa: BLE001 — surface validation errors to the UI
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    state.config_path.write_text(
        yaml.safe_dump(validated.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    state.reload()
    return {"config": validated.model_dump(mode="json")}


@router.get("/doctor", response_model=DoctorOut)
def doctor(state: StateDep) -> DoctorOut:
    c = state.container
    settings = c.settings
    status = c.media_environment.status()
    prov = c.provider
    key_set = bool(os.environ.get(prov.key_env))
    checks = [
        DoctorCheck(name="ffprobe", ok=status.ffprobe_path is not None,
                    detail=status.ffprobe_path or "not found"),
        DoctorCheck(name="ffmpeg", ok=status.ffmpeg_path is not None,
                    detail=status.version or "not found"),
        DoctorCheck(name="ffmpeg libass", ok=status.has_libass,
                    detail="subtitle burn-in available" if status.has_libass
                    else "MISSING — needed for caption/brand"),
        DoctorCheck(name="videotoolbox", ok=status.has_videotoolbox,
                    detail="hw accel available" if status.has_videotoolbox else "unavailable"),
        DoctorCheck(name="input dir", ok=settings.paths.input_dir.exists(),
                    detail=str(settings.paths.input_dir)),
        DoctorCheck(name="font", ok=settings.paths.font.exists(), detail=str(settings.paths.font)),
        DoctorCheck(name="selection", ok=True,
                    detail=f"{prov.provider} · {prov.model}"),
        DoctorCheck(name=f"{prov.provider} key", ok=key_set,
                    detail=f"${prov.key_env} {'set' if key_set else 'NOT set'}"),
    ]
    return DoctorOut(checks=checks)
