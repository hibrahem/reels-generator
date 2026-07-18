"""Silence-removal segment math (pure domain, no mocks)."""

import pytest

from reels.domain.shared.value_objects import TimeRange
from reels.domain.silence_removal.keep_segments import (
    FullySilentVideo,
    compute_keep_segments,
)


def _spans(plan):
    return [(round(s.start, 3), round(s.end, 3)) for s in plan.keep_segments]


def test_video_without_silence_is_kept_whole():
    plan = compute_keep_segments([], 10.0, min_silence=0.6, padding=0.15)
    assert _spans(plan) == [(0.0, 10.0)]
    assert plan.cuts_removed == 0
    assert plan.output_duration == pytest.approx(10.0)


def test_mid_video_silence_is_cut_with_padding_kept_on_both_sides():
    plan = compute_keep_segments(
        [TimeRange(4.0, 6.0)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(0.0, 4.15), (5.85, 10.0)]
    assert plan.cuts_removed == 1
    assert plan.output_duration == pytest.approx(8.3)


def test_silence_shorter_than_minimum_is_left_alone():
    plan = compute_keep_segments(
        [TimeRange(4.0, 4.4)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(0.0, 10.0)]
    assert plan.cuts_removed == 0


def test_silence_at_file_start_is_cut_without_leading_padding():
    plan = compute_keep_segments(
        [TimeRange(0.0, 2.0)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(1.85, 10.0)]
    assert plan.cuts_removed == 1


def test_silence_at_file_end_is_cut_without_trailing_padding():
    plan = compute_keep_segments(
        [TimeRange(8.0, 10.0)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(0.0, 8.15)]
    assert plan.cuts_removed == 1


def test_fully_silent_video_is_rejected():
    with pytest.raises(FullySilentVideo):
        compute_keep_segments([TimeRange(0.0, 10.0)], 10.0, min_silence=0.6, padding=0.15)


def test_overlapping_silences_merge_into_one_cut():
    plan = compute_keep_segments(
        [TimeRange(2.0, 4.0), TimeRange(3.5, 6.0)], 10.0, min_silence=0.6, padding=0.0
    )
    assert _spans(plan) == [(0.0, 2.0), (6.0, 10.0)]
    assert plan.cuts_removed == 1


def test_unsorted_silences_are_handled():
    plan = compute_keep_segments(
        [TimeRange(6.0, 7.0), TimeRange(2.0, 3.0)], 10.0, min_silence=0.6, padding=0.0
    )
    assert _spans(plan) == [(0.0, 2.0), (3.0, 6.0), (7.0, 10.0)]
    assert plan.cuts_removed == 2


def test_padding_wider_than_silence_cancels_the_cut():
    # 0.7s silence, 0.4s padding per side -> nothing left to cut.
    plan = compute_keep_segments(
        [TimeRange(4.0, 4.7)], 10.0, min_silence=0.6, padding=0.4
    )
    assert _spans(plan) == [(0.0, 10.0)]
    assert plan.cuts_removed == 0


def test_tiny_keep_sliver_between_cuts_is_absorbed():
    # 0.03s of audio between two cuts is below the 0.05s sliver floor.
    plan = compute_keep_segments(
        [TimeRange(2.0, 4.0), TimeRange(4.03, 6.0)], 10.0, min_silence=0.6, padding=0.0
    )
    assert _spans(plan) == [(0.0, 2.0), (6.0, 10.0)]
    assert plan.cuts_removed == 1
