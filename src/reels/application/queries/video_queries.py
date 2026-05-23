"""Read-model queries for the UI: video summaries assembled from discovery + manifests."""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.ports.manifest_repository import ManifestRepository
from reels.domain.source_video.repository import SourceVideoRepository


@dataclass(frozen=True, slots=True)
class VideoSummary:
    id: str
    filename: str
    ingested: bool
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool | None
    completed_stages: list[str]
    reel_count: int
    warning_count: int


@dataclass(slots=True)
class ListVideos:
    library: SourceVideoRepository
    manifests: ManifestRepository

    def execute(self) -> list[VideoSummary]:
        summaries: list[VideoSummary] = []
        for source in self.library.discover():
            manifest = self.manifests.load(source.id.value)
            if manifest is None:
                summaries.append(
                    VideoSummary(
                        id=source.id.value,
                        filename=source.path.name,
                        ingested=False,
                        duration_seconds=None,
                        width=None,
                        height=None,
                        fps=None,
                        has_audio=None,
                        completed_stages=[],
                        reel_count=0,
                        warning_count=0,
                    )
                )
                continue
            meta = manifest.source.metadata
            summaries.append(
                VideoSummary(
                    id=manifest.source.id.value,
                    filename=manifest.source.path.name,
                    ingested=meta is not None,
                    duration_seconds=meta.duration_seconds if meta else None,
                    width=meta.resolution.width if meta else None,
                    height=meta.resolution.height if meta else None,
                    fps=meta.fps if meta else None,
                    has_audio=meta.has_audio if meta else None,
                    completed_stages=[s.value for s in manifest.completed_stages],
                    reel_count=len(manifest.reels),
                    warning_count=len(manifest.warnings),
                )
            )
        return summaries
