"""Port for producing a word-level transcript from a source video."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from reels.domain.source_video.source_video import SourceVideo

from .transcript import Transcript


@dataclass(frozen=True, slots=True)
class TranscriptionOptions:
    """Tuning passed to a transcriber. Backend-agnostic by design."""

    model_size: str = "large-v3"
    language: str = "ar"
    device: str = "auto"
    compute_type: str = "auto"
    beam_size: int = 5


class Transcriber(ABC):
    """Produces a word-level :class:`Transcript`. Implemented by infrastructure (faster-whisper)."""

    @abstractmethod
    def transcribe(self, source: SourceVideo, options: TranscriptionOptions) -> Transcript:
        raise NotImplementedError
