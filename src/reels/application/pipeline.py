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
from .use_cases.ingest_videos import IngestVideos
from .use_cases.transcribe_video import TranscribeVideo

# A per-video stage handler advances one manifest by one stage.
StageHandler = Callable[[Manifest], Manifest]


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
    manifests: ManifestRepository
    _handlers: dict[Stage, StageHandler] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        # Register only the per-video stages that exist in this slice.
        self._handlers[Stage.TRANSCRIBE] = self.transcribe.execute

    def run(
        self,
        from_stage: Stage = Stage.INGEST,
        to_stage: Stage = Stage.PACKAGE,
        on_progress: Callable[[PipelineProgress], None] | None = None,
    ) -> list[Manifest]:
        report = on_progress or (lambda _: None)

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

        per_video = [s for s in stages_between(from_stage, to_stage) if s is not Stage.INGEST]
        for manifest in manifests:
            for stage in per_video:
                handler = self._handlers.get(stage)
                if handler is None:
                    raise StageNotBuilt(
                        f"Stage '{stage.value}' is not built yet (later slice). "
                        f"Stopping after the last completed stage for '{manifest.source.id}'."
                    )
                manifest = handler(manifest)
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
