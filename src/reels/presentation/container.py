"""Composition root: the only place that knows about both the use cases and their concrete adapters.

Wiring lives here (not in the domain or application layers) so the dependency rule holds: inner
layers depend on ports, and this outer layer injects the implementations.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reels.application.pipeline import PipelineOrchestrator
from reels.application.use_cases.ingest_videos import IngestVideos
from reels.application.use_cases.transcribe_video import TranscribeVideo
from reels.domain.transcript.transcriber import TranscriptionOptions
from reels.infrastructure.config.settings import Settings, load_settings
from reels.infrastructure.ffmpeg.ffmpeg_media_environment import FFmpegMediaEnvironment
from reels.infrastructure.ffmpeg.ffprobe_video_prober import FFprobeVideoProber
from reels.infrastructure.persistence.filesystem_video_library import FilesystemVideoLibrary
from reels.infrastructure.persistence.json_manifest_repository import JsonManifestRepository
from reels.infrastructure.persistence.json_transcript_repository import JsonTranscriptRepository
from reels.infrastructure.transcription.faster_whisper_transcriber import FasterWhisperTranscriber


@dataclass(slots=True)
class Container:
    """Holds the wired settings and the objects the CLI drives."""

    settings: Settings
    orchestrator: PipelineOrchestrator
    media_environment: FFmpegMediaEnvironment

    @classmethod
    def from_config(cls, config_path: Path) -> Container:
        settings = load_settings(config_path)
        return cls.from_settings(settings)

    @classmethod
    def from_settings(cls, settings: Settings) -> Container:
        work_root = settings.paths.work_dir
        manifests = JsonManifestRepository(work_root=work_root)
        transcripts = JsonTranscriptRepository()
        prober = FFprobeVideoProber()
        library = FilesystemVideoLibrary(
            input_dir=settings.paths.input_dir, work_root=work_root
        )
        transcriber = FasterWhisperTranscriber()

        ingest = IngestVideos(library=library, prober=prober, manifests=manifests)
        transcribe = TranscribeVideo(
            transcriber=transcriber,
            transcripts=transcripts,
            manifests=manifests,
            options=TranscriptionOptions(
                model_size=settings.transcription.model_size,
                language=settings.transcription.language,
                device=settings.transcription.device,
                compute_type=settings.transcription.compute_type,
                beam_size=settings.transcription.beam_size,
            ),
        )
        orchestrator = PipelineOrchestrator(
            ingest=ingest, transcribe=transcribe, manifests=manifests
        )
        return cls(
            settings=settings,
            orchestrator=orchestrator,
            media_environment=FFmpegMediaEnvironment(),
        )
