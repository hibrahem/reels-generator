"""faster-whisper (CTranslate2) implementation of the :class:`Transcriber` port (spec §5.2).

Produces word-level timestamps, which the whole pipeline keys off. Note: CTranslate2 has no
Metal/MPS backend, so on Apple Silicon transcription runs on the CPU (int8). large-v3 on CPU is
accurate but slow; that trade-off is intentional per the spec's Arabic-accuracy priority.
"""

from __future__ import annotations

import logging
import platform

from reels.domain.source_video.source_video import SourceVideo
from reels.domain.transcript.transcriber import Transcriber, TranscriptionOptions
from reels.domain.transcript.transcript import Segment, Transcript, Word

logger = logging.getLogger(__name__)


class FasterWhisperTranscriber(Transcriber):
    def __init__(self, download_root: str | None = None) -> None:
        self._download_root = download_root
        self._model = None  # lazily loaded so importing this module is cheap
        self._loaded_key: tuple[str, str, str] | None = None

    def transcribe(self, source: SourceVideo, options: TranscriptionOptions) -> Transcript:
        device = self._resolve_device(options.device)
        compute_type = self._resolve_compute_type(options.compute_type, device)
        model = self._load_model(options.model_size, device, compute_type)

        logger.info(
            "transcribing %s with %s on %s (%s)",
            source.path.name,
            options.model_size,
            device,
            compute_type,
        )
        segments_iter, info = model.transcribe(
            str(source.path),
            language=options.language,
            beam_size=options.beam_size,
            word_timestamps=True,
            vad_filter=True,
        )

        segments = tuple(self._to_segment(seg) for seg in segments_iter)
        duration = float(getattr(info, "duration", 0.0)) or self._duration_fallback(source)
        return Transcript(
            source_id=source.id.value,
            language=getattr(info, "language", options.language) or options.language,
            duration_seconds=duration,
            segments=segments,
        )

    def _load_model(self, model_size: str, device: str, compute_type: str):
        key = (model_size, device, compute_type)
        if self._model is not None and self._loaded_key == key:
            return self._model
        # Imported here so the heavy native dependency only loads when transcription runs.
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            download_root=self._download_root,
        )
        self._loaded_key = key
        return self._model

    @staticmethod
    def _to_segment(seg) -> Segment:
        words = tuple(
            Word(
                text=w.word,
                start=float(w.start),
                end=float(w.end),
                probability=getattr(w, "probability", None),
            )
            for w in (seg.words or [])
            if w.start is not None and w.end is not None
        )
        return Segment(text=seg.text, start=float(seg.start), end=float(seg.end), words=words)

    @staticmethod
    def _resolve_device(requested: str) -> str:
        if requested != "auto":
            return requested
        # CTranslate2 has no Metal backend; Apple Silicon and Intel Macs both use CPU.
        if platform.system() == "Darwin":
            return "cpu"
        return "cpu"

    @staticmethod
    def _resolve_compute_type(requested: str, device: str) -> str:
        if requested != "auto":
            return requested
        return "int8" if device == "cpu" else "float16"

    @staticmethod
    def _duration_fallback(source: SourceVideo) -> float:
        return source.metadata.duration_seconds if source.metadata else 0.0
