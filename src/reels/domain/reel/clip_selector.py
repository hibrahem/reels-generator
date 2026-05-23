"""Port for the LLM clip-selection stage (text only — never sees pixels)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from reels.domain.transcript.transcript import Transcript

from .clip_selection import ClipCandidate


@dataclass(frozen=True, slots=True)
class SelectionConstraints:
    """Business constraints the selection must respect (validated in code, not just prompted)."""

    min_clip_seconds: float = 20.0
    max_clip_seconds: float = 90.0


class ClipSelector(ABC):
    """Identifies self-contained teaching moments from a transcript.

    Implemented for Claude and OpenAI in infrastructure. The number of clips is content-driven; an
    empty list is a valid answer for a weak source.
    """

    @abstractmethod
    def select_clips(
        self, transcript: Transcript, constraints: SelectionConstraints
    ) -> list[ClipCandidate]:
        raise NotImplementedError
