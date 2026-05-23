"""Port for burning word-by-word captions into a clip (spec §5.7 — highest risk)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CaptionWord:
    """One spoken word, with timing relative to the START of the clip (not the source)."""

    text: str
    start: float
    end: float


class CaptionRenderer(ABC):
    @abstractmethod
    def burn_in(self, video_in: Path, words: list[CaptionWord], out_path: Path) -> None:
        """Render word-by-word captions over the clip, producing a new file at out_path."""
        raise NotImplementedError
