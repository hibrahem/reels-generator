"""The ordered pipeline stages and helpers for resuming with ``--from`` / stopping with ``--to``."""

from __future__ import annotations

from enum import StrEnum


class Stage(StrEnum):
    """The nine pipeline stages, in execution order (spec §4)."""

    INGEST = "ingest"
    TRANSCRIBE = "transcribe"
    SELECT = "select"
    PLAN_LAYOUT = "plan-layout"
    CUT = "cut"
    REFRAME = "reframe"
    CAPTION = "caption"
    BRAND = "brand"
    PACKAGE = "package"

    @property
    def order(self) -> int:
        return STAGE_ORDER.index(self)

    def __ge__(self, other: Stage) -> bool:  # type: ignore[override]
        return self.order >= other.order

    def __gt__(self, other: Stage) -> bool:  # type: ignore[override]
        return self.order > other.order

    def __le__(self, other: Stage) -> bool:  # type: ignore[override]
        return self.order <= other.order

    def __lt__(self, other: Stage) -> bool:  # type: ignore[override]
        return self.order < other.order


STAGE_ORDER: list[Stage] = [
    Stage.INGEST,
    Stage.TRANSCRIBE,
    Stage.SELECT,
    Stage.PLAN_LAYOUT,
    Stage.CUT,
    Stage.REFRAME,
    Stage.CAPTION,
    Stage.BRAND,
    Stage.PACKAGE,
]


def stages_between(start: Stage, end: Stage) -> list[Stage]:
    """Inclusive slice of the pipeline from ``start`` to ``end``."""
    return [s for s in STAGE_ORDER if start <= s <= end]
