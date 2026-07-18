"""Pure segment math for silence removal: detected silences in, keep-segments out."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from reels.domain.shared.exceptions import DomainError
from reels.domain.shared.value_objects import TimeRange

_EPSILON = 1e-3
# Keep-slivers shorter than this are absorbed into the neighboring cut (sub-frame noise).
_MIN_KEEP = 0.05


class FullySilentVideo(DomainError):
    """Removing silence would leave nothing — the whole video is silent."""


@dataclass(frozen=True, slots=True)
class SilenceCutPlan:
    """The segments of the source to keep, in order, and how many cut regions were removed."""

    keep_segments: tuple[TimeRange, ...]
    cuts_removed: int

    @property
    def output_duration(self) -> float:
        return sum(s.duration for s in self.keep_segments)


def compute_keep_segments(
    silences: Sequence[TimeRange],
    video_duration: float,
    *,
    min_silence: float,
    padding: float,
) -> SilenceCutPlan:
    """Turn detected silences into the plan of segments to keep.

    Silences shorter than ``min_silence`` are left alone. Each cut keeps ``padding`` seconds
    of audio on both sides so speech is not clipped — except at the file edges, where there
    is no adjacent speech to protect.
    """
    cuts: list[tuple[float, float]] = []
    for s in sorted(silences, key=lambda s: s.start):
        if s.duration < min_silence:
            continue
        start = 0.0 if s.start <= _EPSILON else s.start + padding
        end = video_duration if s.end >= video_duration - _EPSILON else s.end - padding
        if end - start > _EPSILON:
            cuts.append((max(start, 0.0), min(end, video_duration)))

    merged: list[list[float]] = []
    for start, end in cuts:
        if merged and start <= merged[-1][1] + _MIN_KEEP:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    keep: list[TimeRange] = []
    cursor = 0.0
    for start, end in merged:
        if start - cursor > _MIN_KEEP:
            keep.append(TimeRange(cursor, start))
        cursor = max(cursor, end)
    if video_duration - cursor > _MIN_KEEP:
        keep.append(TimeRange(cursor, video_duration))

    if not keep:
        raise FullySilentVideo(
            f"nothing left to keep: the whole {video_duration:.1f}s video is silent"
        )
    return SilenceCutPlan(keep_segments=tuple(keep), cuts_removed=len(merged))
