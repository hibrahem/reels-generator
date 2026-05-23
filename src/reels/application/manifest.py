"""The per-video pipeline manifest: in-memory state passed between stages and persisted to disk.

State is passed via files plus this manifest, so any stage can be re-run without redoing the ones
before it (spec §4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reels.domain.reel.reel import Reel
from reels.domain.source_video.source_video import SourceVideo

from .pipeline_stage import Stage


@dataclass(slots=True)
class Manifest:
    """Everything known about one source video as it moves through the pipeline."""

    source: SourceVideo
    transcript_path: Path | None = None
    completed_stages: list[Stage] = field(default_factory=list)
    reels: list[Reel] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def mark_completed(self, stage: Stage) -> None:
        if stage not in self.completed_stages:
            self.completed_stages.append(stage)

    def is_completed(self, stage: Stage) -> bool:
        return stage in self.completed_stages

    def flag(self, warning: str) -> None:
        self.warnings.append(warning)
