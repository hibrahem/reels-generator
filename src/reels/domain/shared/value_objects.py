"""Shared kernel value objects.

All value objects are immutable (``frozen=True``) and validate their invariants on construction.
They are pure: no dependency on any framework, I/O, or outer layer.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from .exceptions import (
    InvalidConfidence,
    InvalidCropRectangle,
    InvalidResolution,
    InvalidTimeRange,
)

# Floating-point timestamps from Whisper carry noise; treat differences below this as equal.
_TIME_EPSILON = 1e-3


@dataclass(frozen=True, slots=True)
class TimeRange:
    """A half-open interval of source-video time, measured in seconds."""

    start: float
    end: float

    def __post_init__(self) -> None:
        if self.start < 0:
            raise InvalidTimeRange(f"start must be non-negative, got {self.start}")
        if self.end <= self.start + _TIME_EPSILON:
            raise InvalidTimeRange(
                f"end ({self.end}) must be greater than start ({self.start})"
            )

    @property
    def duration(self) -> float:
        return self.end - self.start

    def overlaps(self, other: TimeRange) -> bool:
        return self.start < other.end - _TIME_EPSILON and other.start < self.end - _TIME_EPSILON

    def contains_instant(self, t: float) -> bool:
        return self.start - _TIME_EPSILON <= t <= self.end + _TIME_EPSILON

    def within(self, bounds: TimeRange) -> bool:
        return (
            self.start >= bounds.start - _TIME_EPSILON
            and self.end <= bounds.end + _TIME_EPSILON
        )


@dataclass(frozen=True, slots=True)
class Resolution:
    """Pixel dimensions of a video frame."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise InvalidResolution(f"dimensions must be positive, got {self.width}x{self.height}")

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    @property
    def is_portrait(self) -> bool:
        return self.height > self.width

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"


@dataclass(frozen=True, slots=True)
class CropRectangle:
    """An axis-aligned crop region in pixels, with top-left origin."""

    x: int
    y: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise InvalidCropRectangle(
                f"crop dimensions must be positive, got {self.width}x{self.height}"
            )
        if self.x < 0 or self.y < 0:
            raise InvalidCropRectangle(f"crop origin must be non-negative, got ({self.x},{self.y})")

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height

    def fits_within(self, resolution: Resolution) -> bool:
        return (
            self.x + self.width <= resolution.width
            and self.y + self.height <= resolution.height
        )

    def clamped_to(self, resolution: Resolution) -> CropRectangle:
        """Return a copy nudged to fit inside ``resolution`` (guards off-by-one drift)."""
        width = min(self.width, resolution.width)
        height = min(self.height, resolution.height)
        x = min(self.x, resolution.width - width)
        y = min(self.y, resolution.height - height)
        return CropRectangle(x=max(x, 0), y=max(y, 0), width=width, height=height)


@dataclass(frozen=True, slots=True)
class Confidence:
    """A probability-like score in the closed interval [0, 1]."""

    value: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.value <= 1.0):
            raise InvalidConfidence(f"confidence must be in [0, 1], got {self.value}")

    def __float__(self) -> float:
        return self.value


@dataclass(frozen=True, slots=True)
class Slug:
    """A filesystem- and URL-safe label derived from human text (Arabic-aware)."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("slug cannot be empty")

    @classmethod
    def from_text(cls, text: str, max_length: int = 40) -> Slug:
        # Keep Arabic letters and ASCII alphanumerics; collapse everything else to hyphens.
        normalized = unicodedata.normalize("NFKC", text).strip().lower()
        kept = re.sub(r"[^\w؀-ۿ]+", "-", normalized, flags=re.UNICODE)
        collapsed = re.sub(r"-{2,}", "-", kept).strip("-")
        truncated = collapsed[:max_length].strip("-")
        return cls(truncated or "clip")

    def __str__(self) -> str:
        return self.value
