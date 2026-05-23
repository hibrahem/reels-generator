"""Linear pipeline orchestration (spec §4): plain Python, no graph/state-machine framework.

The orchestrator runs the ingest stage at the folder level (producing one manifest per video) and
then the per-video stages in order. ``--from`` resumes from a stage by reloading prior manifests;
``--to`` stops early. Stages not yet built raise :class:`StageNotBuilt` so the run halts honestly
at the current slice boundary rather than pretending to succeed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .manifest import Manifest
from .pipeline_stage import Stage, stages_between
from .ports.manifest_repository import ManifestRepository
from .run_options import RunOptions
from .use_cases.brand_reels import BrandReels
from .use_cases.caption_clips import CaptionClips
from .use_cases.cut_clips import CutClips
from .use_cases.ingest_videos import IngestVideos
from .use_cases.package_reels import PackageReels
from .use_cases.plan_layout import PlanLayout
from .use_cases.reframe_clips import ReframeClips
from .use_cases.select_clips import SelectClips
from .use_cases.transcribe_video import TranscribeVideo

# A per-video stage handler advances one manifest by one stage, honoring per-run options.
StageHandler = Callable[[Manifest, RunOptions], Manifest]


class StageNotBuilt(NotImplementedError):
    """A requested stage has not been implemented in the current build slice."""


@dataclass(slots=True)
class PipelineProgress:
    """A single observable step, surfaced to the presentation layer for reporting."""

    stage: Stage
    source_id: str
    message: str


@dataclass(slots=True)
class PipelineOrchestrator:
    ingest: IngestVideos
    transcribe: TranscribeVideo
    select: SelectClips
    plan_layout: PlanLayout
    cut: CutClips
    reframe: ReframeClips
    caption: CaptionClips
    brand: BrandReels
    package: PackageReels
    manifests: ManifestRepository
    _handlers: dict[Stage, StageHandler] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        # Register only the per-video stages that exist in this slice.
        self._handlers[Stage.TRANSCRIBE] = self.transcribe.execute
        self._handlers[Stage.SELECT] = self.select.execute
        self._handlers[Stage.PLAN_LAYOUT] = self.plan_layout.execute
        self._handlers[Stage.CUT] = self.cut.execute
        self._handlers[Stage.REFRAME] = self.reframe.execute
        self._handlers[Stage.CAPTION] = self.caption.execute
        self._handlers[Stage.BRAND] = self.brand.execute
        self._handlers[Stage.PACKAGE] = self.package.execute

    def run(
        self,
        from_stage: Stage = Stage.INGEST,
        to_stage: Stage = Stage.PACKAGE,
        on_progress: Callable[[PipelineProgress], None] | None = None,
        options: RunOptions | None = None,
        video_ids: set[str] | None = None,
    ) -> list[Manifest]:
        report = on_progress or (lambda _: None)
        options = options or RunOptions()

        if from_stage <= Stage.INGEST:
            manifests = self.ingest.execute()
            for m in manifests:
                report(PipelineProgress(Stage.INGEST, m.source.id.value, _ingest_summary(m)))
        else:
            manifests = self.manifests.list_all()
            if not manifests:
                raise StageNotBuilt(
                    f"--from {from_stage.value} needs existing manifests; none found. "
                    "Run ingest first."
                )

        if video_ids is not None:
            manifests = [m for m in manifests if m.source.id.value in video_ids]

        per_video = [s for s in stages_between(from_stage, to_stage) if s is not Stage.INGEST]
        for manifest in manifests:
            for stage in per_video:
                handler = self._handlers.get(stage)
                if handler is None:
                    raise StageNotBuilt(
                        f"Stage '{stage.value}' is not built yet (later slice). "
                        f"Stopping after the last completed stage for '{manifest.source.id}'."
                    )
                manifest = handler(manifest, options)
                report(PipelineProgress(stage, manifest.source.id.value, "done"))

        return manifests


def _ingest_summary(m: Manifest) -> str:
    meta = m.source.metadata
    if meta is None:
        return "ingested"
    return (
        f"{meta.resolution} · {meta.duration_seconds:.0f}s · {meta.fps:.2f}fps · "
        f"{'audio' if meta.has_audio else 'NO AUDIO'}"
    )
