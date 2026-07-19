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


@dataclass(frozen=True, slots=True)
class CaptionLine:
    """One caption phrase — a transcript segment's words, in spoken order.

    Captions follow the transcript's natural phrasing: each segment becomes one line, and
    the renderer may split a line that is too wide for the frame, but never merges lines.
    """

    words: tuple[CaptionWord, ...]


class CaptionRenderer(ABC):
    @abstractmethod
    def burn_in(self, video_in: Path, lines: list[CaptionLine], out_path: Path) -> None:
        """Render word-by-word captions over the clip, producing a new file at out_path."""
        raise NotImplementedError
