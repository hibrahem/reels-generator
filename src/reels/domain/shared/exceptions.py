"""Domain-level exceptions.

These express violations of business invariants in ubiquitous language. They never reference
infrastructure concerns (HTTP, files, ffmpeg, etc.).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain rule violations."""


class InvalidTimeRange(DomainError):
    """A time range violates its invariants (negative, zero-length, or end before start)."""


class InvalidConfidence(DomainError):
    """A confidence value falls outside the closed interval [0, 1]."""


class InvalidResolution(DomainError):
    """A resolution has non-positive dimensions."""


class InvalidCropRectangle(DomainError):
    """A crop rectangle is malformed or does not fit within its frame."""


class ClipOutsideVideo(DomainError):
    """A selected clip falls outside the bounds of its source video."""


class EmptyTranscript(DomainError):
    """An operation requires transcript words but none are present."""
