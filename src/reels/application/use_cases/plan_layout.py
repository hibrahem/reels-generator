"""plan-layout use case (spec §5.4, §6): decide reframe geometry per reel.

v1 implements MODE A (presenter-only). A local vision pass locates the presenter; the domain crop
planner turns that into a concrete 9:16 column, or an anchor-based fallback flagged for review. No
video is written here — only geometry is recorded on the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.run_options import RunOptions, selected_reels
from reels.domain.reel.presenter_detector import PresenterDetector
from reels.domain.services.presenter_crop_planner import PresenterCropPlanner


class CannotPlanLayout(Exception):
    """Raised when layout cannot be planned (e.g. the video was never ingested)."""


@dataclass(slots=True)
class PlanLayout:
    detector: PresenterDetector
    planner: PresenterCropPlanner
    manifests: ManifestRepository
    sample_interval_seconds: float
    anchor: str

    def execute(self, manifest: Manifest, options: RunOptions | None = None) -> Manifest:
        if manifest.source.metadata is None:
            raise CannotPlanLayout(f"'{manifest.source.id}' has no metadata — run ingest first")
        resolution = manifest.source.metadata.resolution

        for reel in selected_reels(manifest, options):
            detection = self.detector.detect(
                manifest.source.path, reel.candidate.time_range, self.sample_interval_seconds
            )
            layout = self.planner.plan_mode_a(resolution, detection, self.anchor)
            reel.warnings = []  # idempotent re-runs: layout is the only source of reel warnings
            reel.plan_layout(layout)

        manifest.mark_completed(Stage.PLAN_LAYOUT)
        self.manifests.save(manifest)
        return manifest
