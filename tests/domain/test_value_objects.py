import pytest

from reels.domain.shared.exceptions import (
    InvalidConfidence,
    InvalidCropRectangle,
    InvalidTimeRange,
)
from reels.domain.shared.value_objects import (
    Confidence,
    CropRectangle,
    Resolution,
    Slug,
    TimeRange,
)


def test_time_range_rejects_end_before_start():
    with pytest.raises(InvalidTimeRange):
        TimeRange(start=10.0, end=5.0)


def test_time_range_rejects_zero_length():
    with pytest.raises(InvalidTimeRange):
        TimeRange(start=5.0, end=5.0)


def test_time_range_duration_and_overlap():
    a = TimeRange(start=0.0, end=10.0)
    b = TimeRange(start=9.0, end=20.0)
    c = TimeRange(start=10.0, end=15.0)
    assert a.duration == 10.0
    assert a.overlaps(b)
    assert not a.overlaps(c)  # touching boundaries do not overlap


def test_time_range_within_bounds():
    bounds = TimeRange(start=0.0, end=100.0)
    assert TimeRange(start=10.0, end=20.0).within(bounds)
    assert not TimeRange(start=90.0, end=120.0).within(bounds)


def test_confidence_bounds():
    assert float(Confidence(0.0)) == 0.0
    assert float(Confidence(1.0)) == 1.0
    with pytest.raises(InvalidConfidence):
        Confidence(1.5)


def test_crop_rectangle_fits_within_and_clamps():
    res = Resolution(width=1920, height=1080)
    crop = CropRectangle(x=1800, y=0, width=300, height=1080)
    assert not crop.fits_within(res)
    clamped = crop.clamped_to(res)
    assert clamped.fits_within(res)


def test_crop_rectangle_rejects_negative_origin():
    with pytest.raises(InvalidCropRectangle):
        CropRectangle(x=-1, y=0, width=10, height=10)


def test_resolution_aspect_ratio_and_portrait():
    assert Resolution(1920, 1080).is_portrait is False
    assert Resolution(1080, 1920).is_portrait is True


def test_slug_keeps_arabic_and_ascii():
    assert str(Slug.from_text("Hello World!")) == "hello-world"
    arabic = Slug.from_text("الدرس الأول")
    assert str(arabic)  # non-empty; Arabic letters preserved
    assert " " not in str(arabic)


def test_slug_falls_back_when_empty():
    assert str(Slug.from_text("!!!")) == "clip"
