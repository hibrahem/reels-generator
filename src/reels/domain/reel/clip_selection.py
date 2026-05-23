"""Value objects describing an LLM-selected teaching moment."""

from __future__ import annotations

from dataclasses import dataclass

from reels.domain.shared.value_objects import Confidence, TimeRange


@dataclass(frozen=True, slots=True)
class ClipCandidate:
    """A self-contained teaching moment proposed by the selection stage.

    The LLM sees text only; it never decides crop geometry. ``visual_dependent`` is a *hint* to the
    layout stage about whether slides matter for this moment — not the final reframe decision.
    """

    time_range: TimeRange
    title: str
    hook: str
    caption: str
    reason: str
    confidence: Confidence
    visual_dependent: bool = False

    @property
    def duration(self) -> float:
        return self.time_range.duration
