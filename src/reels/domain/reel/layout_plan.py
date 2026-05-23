"""Reframe modes and the concrete geometry plan for turning a 16:9 clip into 9:16."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from reels.domain.shared.value_objects import CropRectangle


class ReframeMode(StrEnum):
    """How a clip is reframed to vertical.

    PRESENTER_ONLY (MODE A): a 9:16 column anchored on the detected presenter region.
    STACKED (MODE B): slides cropped on top, presenter on the bottom, composited into 9:16.
    """

    PRESENTER_ONLY = "presenter_only"  # MODE A
    STACKED = "stacked"  # MODE B


@dataclass(frozen=True, slots=True)
class PresenterDetection:
    """Result of the local vision pass: where the presenter is and how steady that box is."""

    box: CropRectangle | None
    stability: float  # 0..1; higher means the box barely moved across sampled frames
    sampled_frames: int

    @property
    def is_reliable(self) -> bool:
        return self.box is not None and self.stability >= 0.6


@dataclass(frozen=True, slots=True)
class LayoutPlan:
    """Concrete pixel geometry for reframing one clip (produced by plan-layout, used by reframe)."""

    mode: ReframeMode
    presenter_crop: CropRectangle
    slide_crop: CropRectangle | None = None  # required for STACKED, ignored for PRESENTER_ONLY
    fallback_used: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.mode is ReframeMode.STACKED and self.slide_crop is None:
            raise ValueError("STACKED layout requires a slide_crop")
