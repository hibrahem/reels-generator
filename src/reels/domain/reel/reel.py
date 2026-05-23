"""The Reel aggregate root: one teaching moment as it moves through the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from reels.domain.shared.value_objects import Slug

from .clip_selection import ClipCandidate
from .layout_plan import LayoutPlan, ReframeMode


@dataclass(slots=True)
class Reel:
    """Aggregate root for a single reel.

    Carries the selected moment (:class:`ClipCandidate`), the layout decision, and the paths to
    intermediate and finished artifacts. State advances stage by stage; the manifest persists it so
    any stage can resume. All mutation goes through intention-revealing methods, never raw setters.
    """

    source_id: str
    index: int  # 1-based position within the source, used in the output filename (NN)
    candidate: ClipCandidate
    layout: LayoutPlan | None = None
    cut_path: Path | None = None
    reframed_path: Path | None = None
    captioned_path: Path | None = None
    final_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def slug(self) -> Slug:
        return Slug.from_text(self.candidate.title)

    @property
    def mode(self) -> ReframeMode | None:
        return self.layout.mode if self.layout else None

    def output_filename(self) -> str:
        """Stable naming scheme: ``{source}__{NN}__{slug}.mp4`` (spec §5.9)."""
        return f"{self.source_id}__{self.index:02d}__{self.slug}.mp4"

    def plan_layout(self, layout: LayoutPlan) -> None:
        self.layout = layout
        self.warnings.extend(layout.warnings)

    def record_cut(self, path: Path) -> None:
        self.cut_path = path

    def record_reframe(self, path: Path) -> None:
        self.reframed_path = path

    def record_captioned(self, path: Path) -> None:
        self.captioned_path = path

    def finalize(self, path: Path) -> None:
        self.final_path = path

    def flag(self, warning: str) -> None:
        """Attach a human-reviewable warning (e.g. unstable detection, fallback crop used)."""
        self.warnings.append(warning)
