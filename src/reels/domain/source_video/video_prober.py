"""Port for probing a video file's technical metadata (implemented via ffprobe)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .video_metadata import VideoMetadata


class VideoProber(ABC):
    """Reads duration, resolution, fps, and audio info from a video file. Never hardcodes them."""

    @abstractmethod
    def probe(self, path: Path) -> VideoMetadata:
        raise NotImplementedError
