"""FFmpeg silencedetect implementation of the SilenceDetector port."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from reels.application.ports.silence_detector import SilenceDetector
from reels.domain.shared.value_objects import TimeRange

logger = logging.getLogger(__name__)

_EPSILON = 1e-3
_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


class SilenceDetectError(RuntimeError):
    """The ffmpeg silencedetect pass failed."""


def parse_silencedetect(stderr: str, duration: float) -> list[TimeRange]:
    """Pair silence_start/silence_end lines; an unmatched trailing start runs to the file end."""
    intervals: list[TimeRange] = []
    start: float | None = None
    for line in stderr.splitlines():
        m = _START.search(line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = _END.search(line)
        if m and start is not None:
            end = min(duration, float(m.group(1)))
            if end > start + _EPSILON:
                intervals.append(TimeRange(start, end))
            start = None
    if start is not None and duration > start + _EPSILON:
        intervals.append(TimeRange(start, duration))
    return intervals


class FFmpegSilenceDetector(SilenceDetector):
    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def detect(
        self, video_path: Path, *, threshold_db: float, min_silence: float, duration: float
    ) -> list[TimeRange]:
        # silencedetect logs its results at loglevel info — do not lower the loglevel here.
        cmd = [
            self._ffmpeg, "-hide_banner", "-nostats",
            "-i", str(video_path),
            "-vn", "-af", f"silencedetect=noise={threshold_db}dB:d={min_silence}",
            "-f", "null", "-",
        ]
        logger.info("ffmpeg %s", " ".join(cmd[1:]))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise SilenceDetectError("ffmpeg binary not found") from exc
        except subprocess.CalledProcessError as exc:
            raise SilenceDetectError(
                f"silence detection failed: {exc.stderr.strip()[-500:]}"
            ) from exc
        return parse_silencedetect(proc.stderr, duration)
