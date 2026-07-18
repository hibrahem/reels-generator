"""Port for detecting silent passages in a video's audio track."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from reels.domain.shared.value_objects import TimeRange


class SilenceDetector(ABC):
    @abstractmethod
    def detect(
        self, video_path: Path, *, threshold_db: float, min_silence: float, duration: float
    ) -> list[TimeRange]:
        """Return intervals where audio stays below ``threshold_db`` for >= ``min_silence`` s.

        ``duration`` is the video's total length, used to close a silence that runs to the end.
        """
        raise NotImplementedError
