"""Composition root: the only place that knows about both the use cases and their concrete adapters.

Wiring lives here (not in the domain or application layers) so the dependency rule holds: inner
layers depend on ports, and this outer layer injects the implementations.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from reels.application.pipeline import PipelineOrchestrator
from reels.application.ports.video_editor import RenderSpec
from reels.application.use_cases.caption_clips import CaptionClips
from reels.application.use_cases.cut_clips import CutClips
from reels.application.use_cases.ingest_videos import IngestVideos
from reels.application.use_cases.plan_layout import PlanLayout
from reels.application.use_cases.reframe_clips import ReframeClips
from reels.application.use_cases.select_clips import SelectClips
from reels.application.use_cases.transcribe_video import TranscribeVideo
from reels.domain.reel.clip_selector import ClipSelector, SelectionConstraints
from reels.domain.services.clip_reconciliation import ClipReconciliationService
from reels.domain.services.presenter_crop_planner import PresenterCropPlanner
from reels.domain.shared.value_objects import Resolution
from reels.domain.transcript.transcriber import TranscriptionOptions
from reels.infrastructure.captions.ass_subtitle_builder import CaptionStyle
from reels.infrastructure.captions.libass_caption_renderer import LibassCaptionRenderer
from reels.infrastructure.config.settings import Settings, load_settings
from reels.infrastructure.detection.opencv_presenter_detector import OpenCVPresenterDetector
from reels.infrastructure.ffmpeg.ffmpeg_media_environment import FFmpegMediaEnvironment
from reels.infrastructure.ffmpeg.ffmpeg_video_editor import FFmpegVideoEditor
from reels.infrastructure.ffmpeg.ffprobe_video_prober import FFprobeVideoProber
from reels.infrastructure.llm.errors import SelectionUnavailable
from reels.infrastructure.llm.lazy import LazyClipSelector
from reels.infrastructure.llm.provider_profiles import PROVIDER_PROFILES, ProviderProfile
from reels.infrastructure.persistence.filesystem_video_library import FilesystemVideoLibrary
from reels.infrastructure.persistence.json_manifest_repository import JsonManifestRepository
from reels.infrastructure.persistence.json_transcript_repository import JsonTranscriptRepository
from reels.infrastructure.transcription.faster_whisper_transcriber import FasterWhisperTranscriber


@dataclass(frozen=True, slots=True)
class ResolvedProvider:
    """The effective selection settings after applying profile defaults and config/env overrides."""

    provider: str
    model: str
    base_url: str | None
    key_env: str
    openai_compatible: bool


@dataclass(slots=True)
class Container:
    """Holds the wired settings and the objects the CLI drives."""

    settings: Settings
    orchestrator: PipelineOrchestrator
    media_environment: FFmpegMediaEnvironment
    provider: ResolvedProvider

    @classmethod
    def from_config(cls, config_path: Path) -> Container:
        # Load .env (token + optional overrides) before reading any environment variables.
        load_dotenv()
        settings = load_settings(config_path)
        return cls.from_settings(settings)

    @classmethod
    def from_settings(cls, settings: Settings) -> Container:
        work_root = settings.paths.work_dir
        manifests = JsonManifestRepository(work_root=work_root)
        transcripts = JsonTranscriptRepository()
        prober = FFprobeVideoProber()
        library = FilesystemVideoLibrary(input_dir=settings.paths.input_dir, work_root=work_root)
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

        provider = _resolve_provider(settings)
        select = SelectClips(
            transcripts=transcripts,
            selector=LazyClipSelector(lambda: _build_selector(settings, provider)),
            reconciliation=ClipReconciliationService(),
            manifests=manifests,
            constraints=SelectionConstraints(
                min_clip_seconds=settings.selection.min_clip_seconds,
                max_clip_seconds=settings.selection.max_clip_seconds,
            ),
        )

        ffmpeg_path = str(settings.paths.ffmpeg) if settings.paths.ffmpeg else None
        render_spec = RenderSpec(
            resolution=Resolution(settings.output.width, settings.output.height),
            video_codec=settings.output.video_codec,
            audio_codec=settings.output.audio_codec,
            video_bitrate=settings.output.video_bitrate,
            audio_bitrate=settings.output.audio_bitrate,
            faststart=settings.output.faststart,
        )
        editor = FFmpegVideoEditor(render_spec, ffmpeg_path=ffmpeg_path)
        caption_renderer = LibassCaptionRenderer(
            style=_caption_style(settings),
            fonts_dir=settings.paths.font.parent,
            spec=render_spec,
            ffmpeg_path=ffmpeg_path,
        )
        plan_layout = PlanLayout(
            detector=OpenCVPresenterDetector(),
            planner=PresenterCropPlanner(),
            manifests=manifests,
            sample_interval_seconds=settings.layout.detection_sample_interval_seconds,
            anchor=settings.layout.presenter_anchor,
        )
        cut = CutClips(editor=editor, manifests=manifests)
        reframe = ReframeClips(editor=editor, manifests=manifests)
        caption = CaptionClips(
            transcripts=transcripts, renderer=caption_renderer, manifests=manifests
        )

        orchestrator = PipelineOrchestrator(
            ingest=ingest,
            transcribe=transcribe,
            select=select,
            plan_layout=plan_layout,
            cut=cut,
            reframe=reframe,
            caption=caption,
            manifests=manifests,
        )
        return cls(
            settings=settings,
            orchestrator=orchestrator,
            media_environment=FFmpegMediaEnvironment(ffmpeg_path=ffmpeg_path),
            provider=provider,
        )


def _resolve_provider(settings: Settings) -> ResolvedProvider:
    sel = settings.selection
    profile: ProviderProfile = PROVIDER_PROFILES[sel.provider]
    # Precedence: env override > config.yaml > provider default.
    model = os.environ.get("REELS_SELECTION_MODEL") or sel.model or profile.default_model
    base_url = os.environ.get("REELS_SELECTION_BASE_URL") or sel.base_url or profile.base_url
    key_env = sel.api_key_env or profile.key_env
    return ResolvedProvider(
        provider=sel.provider,
        model=model,
        base_url=base_url,
        key_env=key_env,
        openai_compatible=profile.openai_compatible,
    )


def _caption_style(settings: Settings) -> CaptionStyle:
    c = settings.captions
    return CaptionStyle(
        font_family=c.font_family,
        base_font_size=c.base_font_size,
        active_font_size=c.active_font_size,
        base_color=c.base_color,
        active_color=c.active_color,
        position=c.position,
        safe_margin_v=c.safe_margin_v,
        safe_margin_h=c.safe_margin_h,
        max_words_per_line=c.max_words_per_line,
        outline=c.outline,
        shadow=c.shadow,
        play_res_x=settings.output.width,
        play_res_y=settings.output.height,
        bold=c.bold,
        box=c.box,
        box_color=c.box_color,
    )


def _build_selector(settings: Settings, provider: ResolvedProvider) -> ClipSelector:
    api_key = os.environ.get(provider.key_env)
    if not api_key:
        raise SelectionUnavailable(
            f"selection provider '{provider.provider}' needs ${provider.key_env}, "
            "which is not set. Add it to a .env file or export it."
        )
    if provider.openai_compatible:
        from reels.infrastructure.llm.openai_compatible_clip_selector import (
            OpenAICompatibleClipSelector,
        )

        return OpenAICompatibleClipSelector(
            api_key=api_key,
            model=provider.model,
            base_url=provider.base_url,
            temperature=settings.selection.temperature,
            max_retries=settings.selection.max_retries,
        )

    from reels.infrastructure.llm.claude_clip_selector import ClaudeClipSelector

    return ClaudeClipSelector(
        api_key=api_key,
        model=provider.model,
        temperature=settings.selection.temperature,
        max_retries=settings.selection.max_retries,
    )
