"""Domain service: enforce the business rules on a raw set of selected clips.

This is stateless logic that spans multiple ClipCandidates, so it lives in a domain service rather
than on a single entity. It is pure — selection adapters call it after the LLM returns.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.clip_selector import SelectionConstraints
from reels.domain.shared.value_objects import TimeRange


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """The accepted clips plus a human-readable log of what was dropped or adjusted."""

    accepted: list[ClipCandidate]
    notes: list[str]


class ClipReconciliationService:
    """Applies duration limits, in-bounds clamping, word-boundary snapping, and overlap removal."""

    def reconcile(
        self,
        candidates: list[ClipCandidate],
        constraints: SelectionConstraints,
        video_span: TimeRange,
        snap_start: Callable[[float], float],
        snap_end: Callable[[float], float],
    ) -> ReconciliationResult:
        notes: list[str] = []
        snapped: list[ClipCandidate] = []

        for candidate in candidates:
            clip = self._snap_into_bounds(candidate, video_span, snap_start, snap_end, notes)
            if clip is None:
                continue
            if not self._within_duration_window(clip, constraints, notes):
                continue
            snapped.append(clip)

        accepted = self._drop_overlaps(snapped, notes)
        accepted.sort(key=lambda c: c.time_range.start)
        return ReconciliationResult(accepted=accepted, notes=notes)

    def _snap_into_bounds(
        self,
        candidate: ClipCandidate,
        video_span: TimeRange,
        snap_start: Callable[[float], float],
        snap_end: Callable[[float], float],
        notes: list[str],
    ) -> ClipCandidate | None:
        start = max(candidate.time_range.start, video_span.start)
        end = min(candidate.time_range.end, video_span.end)
        try:
            snapped_range = TimeRange(start=snap_start(start), end=snap_end(end))
        except Exception:
            notes.append(f"dropped '{candidate.title}': could not snap to word boundaries")
            return None
        if not snapped_range.within(video_span):
            notes.append(f"dropped '{candidate.title}': falls outside video duration")
            return None
        return _replace_range(candidate, snapped_range)

    def _within_duration_window(
        self, clip: ClipCandidate, constraints: SelectionConstraints, notes: list[str]
    ) -> bool:
        duration = clip.duration
        if duration < constraints.min_clip_seconds:
            notes.append(
                f"dropped '{clip.title}': {duration:.1f}s below min {constraints.min_clip_seconds}s"
            )
            return False
        if duration > constraints.max_clip_seconds:
            notes.append(
                f"dropped '{clip.title}': {duration:.1f}s above max {constraints.max_clip_seconds}s"
            )
            return False
        return True

    def _drop_overlaps(
        self, clips: list[ClipCandidate], notes: list[str]
    ) -> list[ClipCandidate]:
        # Highest confidence wins; on ties, the longer clip wins.
        ranked = sorted(clips, key=lambda c: (float(c.confidence), c.duration), reverse=True)
        kept: list[ClipCandidate] = []
        for clip in ranked:
            if any(clip.time_range.overlaps(other.time_range) for other in kept):
                notes.append(f"dropped '{clip.title}': overlaps a higher-confidence clip")
                continue
            kept.append(clip)
        return kept


def _replace_range(candidate: ClipCandidate, time_range: TimeRange) -> ClipCandidate:
    return ClipCandidate(
        time_range=time_range,
        title=candidate.title,
        hook=candidate.hook,
        caption=candidate.caption,
        reason=candidate.reason,
        confidence=candidate.confidence,
        visual_dependent=candidate.visual_dependent,
    )
