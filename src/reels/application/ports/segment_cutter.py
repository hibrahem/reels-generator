"""Port for rendering a copy of a video that keeps only the given segments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from reels.domain.shared.value_objects import TimeRange


class SegmentCutter(ABC):
    @abstractmethod
    def cut(self, video_path: Path, segments: Sequence[TimeRange], out_path: Path) -> None:
        """Write ``out_path`` keeping only ``segments`` of ``video_path``, concatenated in order."""
        raise NotImplementedError
