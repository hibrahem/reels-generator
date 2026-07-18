"""Use case: produce a copy of a video with its silent passages removed.

Standalone tool — not part of the reels pipeline (no manifest, no stages).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from reels.application.ports.segment_cutter import SegmentCutter
from reels.application.ports.silence_detector import SilenceDetector
from reels.domain.silence_removal.keep_segments import compute_keep_segments
from reels.domain.source_video.video_prober import VideoProber


class NoAudioTrack(Exception):
    """The video has no audio stream, so silence removal cannot apply."""


@dataclass(frozen=True, slots=True)
class SilenceRemovalSettings:
    threshold_db: float = -35.0
    min_silence: float = 0.6
    padding: float = 0.15


@dataclass(frozen=True, slots=True)
class SilenceRemovalResult:
    original_duration: float
    output_duration: float
    cuts_removed: int


ProgressFn = Callable[[str, str], None]


class RemoveSilence:
    def __init__(
        self, *, prober: VideoProber, detector: SilenceDetector, cutter: SegmentCutter
    ) -> None:
        self._prober = prober
        self._detector = detector
        self._cutter = cutter

    def execute(
        self,
        video_path: Path,
        out_path: Path,
        settings: SilenceRemovalSettings | None = None,
        on_progress: ProgressFn | None = None,
    ) -> SilenceRemovalResult:
        settings = settings or SilenceRemovalSettings()
        emit: ProgressFn = on_progress or (lambda stage, message: None)

        emit("probe", "reading video metadata")
        meta = self._prober.probe(video_path)
        if not meta.has_audio:
            raise NoAudioTrack("this video has no audio track")

        emit("detect", "detecting silences")
        silences = self._detector.detect(
            video_path,
            threshold_db=settings.threshold_db,
            min_silence=settings.min_silence,
            duration=meta.duration_seconds,
        )
        plan = compute_keep_segments(
            silences,
            meta.duration_seconds,
            min_silence=settings.min_silence,
            padding=settings.padding,
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if plan.cuts_removed == 0:
            shutil.copyfile(video_path, out_path)
            return SilenceRemovalResult(meta.duration_seconds, meta.duration_seconds, 0)

        emit("cut", f"removing {plan.cuts_removed} silent passage(s)")
        self._cutter.cut(video_path, plan.keep_segments, out_path)
        return SilenceRemovalResult(
            original_duration=meta.duration_seconds,
            output_duration=plan.output_duration,
            cuts_removed=plan.cuts_removed,
        )
