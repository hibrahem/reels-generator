"""Transcribe use case (spec §5.2): produce a word-level transcript and persist it."""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.domain.transcript.transcriber import Transcriber, TranscriptionOptions


class CannotTranscribe(Exception):
    """Raised when a video cannot be transcribed (e.g. it was never ingested)."""


@dataclass(slots=True)
class TranscribeVideo:
    """Transcribes one ingested source video and records the transcript path on its manifest."""

    transcriber: Transcriber
    transcripts: TranscriptRepository
    manifests: ManifestRepository
    options: TranscriptionOptions

    def execute(self, manifest: Manifest) -> Manifest:
        if not manifest.source.is_ingested:
            raise CannotTranscribe(
                f"'{manifest.source.id}' has no metadata — run ingest first"
            )
        manifest.source.working_dir.mkdir(parents=True, exist_ok=True)
        transcript = self.transcriber.transcribe(manifest.source, self.options)
        if not transcript.has_words():
            manifest.flag("transcript has no word-level timings — downstream stages will fail")
        manifest.transcript_path = self.transcripts.save(transcript, manifest.source.working_dir)
        manifest.mark_completed(Stage.TRANSCRIBE)
        self.manifests.save(manifest)
        return manifest
