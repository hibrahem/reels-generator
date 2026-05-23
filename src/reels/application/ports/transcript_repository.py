"""Port for persisting the raw word-level transcript as JSON in the working dir."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from reels.domain.transcript.transcript import Transcript


class TranscriptRepository(ABC):
    @abstractmethod
    def save(self, transcript: Transcript, working_dir: Path) -> Path:
        """Persist the transcript (words + timestamps + segments) and return its path."""
        raise NotImplementedError

    @abstractmethod
    def load(self, path: Path) -> Transcript:
        raise NotImplementedError
