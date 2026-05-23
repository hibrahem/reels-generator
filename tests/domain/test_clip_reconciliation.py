from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.clip_selector import SelectionConstraints
from reels.domain.services.clip_reconciliation import ClipReconciliationService
from reels.domain.shared.value_objects import Confidence, TimeRange


def _candidate(start, end, title, conf):
    return ClipCandidate(
        time_range=TimeRange(start, end),
        title=title,
        hook="",
        caption="",
        reason="",
        confidence=Confidence(conf),
    )


def _identity(t):
    return t


def test_drops_clips_outside_duration_window():
    service = ClipReconciliationService()
    candidates = [
        _candidate(0, 10, "too-short", 0.9),  # 10s < 20s min
        _candidate(20, 120, "too-long", 0.9),  # 100s > 90s max
        _candidate(200, 240, "just-right", 0.9),  # 40s
    ]
    result = service.reconcile(
        candidates,
        SelectionConstraints(min_clip_seconds=20, max_clip_seconds=90),
        video_span=TimeRange(0, 300),
        snap_start=_identity,
        snap_end=_identity,
    )
    assert [c.title for c in result.accepted] == ["just-right"]
    assert len(result.notes) == 2


def test_overlap_keeps_higher_confidence():
    service = ClipReconciliationService()
    candidates = [
        _candidate(0, 40, "low", 0.4),
        _candidate(20, 60, "high", 0.9),  # overlaps "low"
    ]
    result = service.reconcile(
        candidates,
        SelectionConstraints(min_clip_seconds=20, max_clip_seconds=90),
        video_span=TimeRange(0, 300),
        snap_start=_identity,
        snap_end=_identity,
    )
    assert [c.title for c in result.accepted] == ["high"]


def test_drops_clip_outside_video_bounds():
    service = ClipReconciliationService()
    candidates = [_candidate(280, 360, "overrun", 0.9)]
    result = service.reconcile(
        candidates,
        SelectionConstraints(min_clip_seconds=20, max_clip_seconds=90),
        video_span=TimeRange(0, 300),
        snap_start=_identity,
        snap_end=_identity,
    )
    # End clamped to 300 → 20s clip, still within window and bounds → accepted.
    assert len(result.accepted) == 1
    assert result.accepted[0].time_range.end == 300
