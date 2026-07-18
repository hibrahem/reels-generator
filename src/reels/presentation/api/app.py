"""FastAPI application factory — a web delivery adapter over the existing pipeline.

Handlers stay thin: they build/refresh the Container and call use cases. No business logic here.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .state import AppState

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_SPA_DIST = _PROJECT_ROOT / "web" / "dist"


def create_app(config_path: Path) -> FastAPI:
    app = FastAPI(title="Reels Studio", version="0.1.0")
    app.state.reels = AppState(config_path)

    # Local single-user tool; allow the Vite dev server and same-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from .routers import jobs, silence, system, videos

    app.include_router(system.router, prefix="/api", tags=["system"])
    app.include_router(videos.router, prefix="/api", tags=["videos"])
    app.include_router(jobs.router, prefix="/api", tags=["jobs"])
    app.include_router(silence.router, prefix="/api", tags=["silence"])

    # Serve the built SPA if present (prod/local single-process mode).
    if _SPA_DIST.exists():
        app.mount("/", StaticFiles(directory=_SPA_DIST, html=True), name="spa")

    return app
