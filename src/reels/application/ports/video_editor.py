"""Port for the video-editing operations the pipeline needs (cut, reframe). FFmpeg implements it."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from reels.domain.reel.layout_plan import LayoutPlan
from reels.domain.shared.value_objects import Resolution, TimeRange


@dataclass(frozen=True, slots=True)
class RenderSpec:
    """The consistent output spec applied when (re-)encoding (spec §5.8)."""

    resolution: Resolution
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    video_bitrate: str = "8M"
    audio_bitrate: str = "192k"
    faststart: bool = True


class VideoEditor(ABC):
    @abstractmethod
    def cut(self, source_path: Path, time_range: TimeRange, out_path: Path) -> None:
        """Extract [start, end] from the source with an accurate (re-encoded) cut (spec §5.5)."""
        raise NotImplementedError

    @abstractmethod
    def reframe(self, in_path: Path, layout: LayoutPlan, out_path: Path) -> None:
        """Apply the layout geometry, producing a vertical clip at the render resolution (§5.6)."""
        raise NotImplementedError
