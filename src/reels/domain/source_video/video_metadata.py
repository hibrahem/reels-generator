"""Value object describing the technical properties of a source video."""

from __future__ import annotations

from dataclasses import dataclass

from reels.domain.shared.value_objects import Resolution, TimeRange


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Probed technical facts about a source video. Read per file, never hardcoded."""

    duration_seconds: float
    resolution: Resolution
    fps: float
    has_audio: bool
    video_codec: str | None = None
    audio_codec: str | None = None

    @property
    def full_span(self) -> TimeRange:
        """The time range covering the whole video."""
        return TimeRange(start=0.0, end=self.duration_seconds)
