"""Port for locally detecting the presenter's position within a clip."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from reels.domain.shared.value_objects import TimeRange

from .layout_plan import PresenterDetection


class PresenterDetector(ABC):
    """Locates the presenter bounding box across sampled frames of a clip.

    Detection runs locally (OpenCV/mediapipe). It must degrade gracefully: when detection is
    unstable or fails, it returns a low-stability / empty result so the caller can fall back to a
    configured default crop and flag the reel for human review (spec §6).
    """

    @abstractmethod
    def detect(
        self, video_path: Path, span: TimeRange, sample_interval_seconds: float
    ) -> PresenterDetection:
        raise NotImplementedError
