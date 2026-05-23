"""Domain service: turn a presenter detection into concrete MODE A crop geometry.

Pure geometry, no I/O. Computes a vertical (target-aspect) column anchored on the detected
presenter; when detection is unreliable it falls back to an anchor-based column and flags the reel
for human review (spec §6: a wrong-but-reviewable crop beats a crash).
"""

from __future__ import annotations

from reels.domain.reel.layout_plan import LayoutPlan, PresenterDetection, ReframeMode
from reels.domain.shared.value_objects import CropRectangle, Resolution

# 9:16 vertical target.
_TARGET_W, _TARGET_H = 9, 16


class PresenterCropPlanner:
    def plan_mode_a(
        self,
        resolution: Resolution,
        detection: PresenterDetection,
        anchor: str = "right",
    ) -> LayoutPlan:
        # A full-height 9:16 column. If the source is narrower than 9:16, fall back to full width
        # and reduce height to keep the aspect (rare for 16:9 sources).
        desired_width = self._even(round(resolution.height * _TARGET_W / _TARGET_H))
        if desired_width <= resolution.width:
            column_width, height = desired_width, resolution.height
        else:
            column_width = self._even(resolution.width)
            height = min(resolution.height, self._even(round(column_width * _TARGET_H / _TARGET_W)))

        warnings: list[str] = []
        fallback = not detection.is_reliable or detection.box is None
        if fallback:
            warnings.append(
                f"presenter detection unreliable (stability={detection.stability:.2f}); "
                f"used {anchor}-anchored fallback crop — review this reel"
            )
            x = self._anchor_x(anchor, resolution.width, column_width)
        else:
            center_x = detection.box.x + detection.box.width // 2
            x = center_x - column_width // 2

        x = max(0, min(x, resolution.width - column_width))
        crop = CropRectangle(x=x, y=0, width=column_width, height=height).clamped_to(resolution)
        return LayoutPlan(
            mode=ReframeMode.PRESENTER_ONLY,
            presenter_crop=crop,
            fallback_used=fallback,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _anchor_x(anchor: str, frame_width: int, column_width: int) -> int:
        if anchor == "left":
            return 0
        if anchor == "center":
            return (frame_width - column_width) // 2
        return frame_width - column_width  # right (default for this series)

    @staticmethod
    def _even(value: int) -> int:
        # H.264 / yuv420p needs even dimensions.
        return value if value % 2 == 0 else value - 1
