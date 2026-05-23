"""Ingest use case (spec §5.1): discover source videos and record their probed metadata."""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.domain.source_video.repository import SourceVideoRepository
from reels.domain.source_video.video_prober import VideoProber


@dataclass(slots=True)
class IngestVideos:
    """Scans the input folder, probes each video, and creates/updates its manifest."""

    library: SourceVideoRepository
    prober: VideoProber
    manifests: ManifestRepository

    def execute(self) -> list[Manifest]:
        ingested: list[Manifest] = []
        for discovered in self.library.discover():
            manifest = self.manifests.load(discovered.id.value) or Manifest(source=discovered)
            metadata = self.prober.probe(manifest.source.path)
            manifest.source.describe(metadata)
            if not metadata.has_audio:
                manifest.flag("no audio stream detected — transcription will produce nothing")
            manifest.mark_completed(Stage.INGEST)
            self.manifests.save(manifest)
            ingested.append(manifest)
        return ingested
