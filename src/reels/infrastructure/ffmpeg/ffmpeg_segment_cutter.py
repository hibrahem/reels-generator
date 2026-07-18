"""FFmpeg trim+concat implementation of the SegmentCutter port."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from reels.application.ports.segment_cutter import SegmentCutter
from reels.domain.shared.value_objects import TimeRange

logger = logging.getLogger(__name__)


class SegmentCutError(RuntimeError):
    """The ffmpeg render pass failed."""


def segments_filtergraph(segments: Sequence[TimeRange]) -> str:
    """Trim each keep-segment (video+audio), reset timestamps, and concat them in order."""
    parts: list[str] = []
    labels = ""
    for i, seg in enumerate(segments):
        span = f"start={seg.start:.3f}:end={seg.end:.3f}"
        parts.append(f"[0:v]trim={span},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim={span},asetpts=PTS-STARTPTS[a{i}]")
        labels += f"[v{i}][a{i}]"
    parts.append(f"{labels}concat=n={len(segments)}:v=1:a=1[vout][aout]")
    return ";".join(parts)


class FFmpegSegmentCutter(SegmentCutter):
    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def cut(self, video_path: Path, segments: Sequence[TimeRange], out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_path),
            "-filter_complex", segments_filtergraph(segments),
            "-map", "[vout]", "-map", "[aout]",
            # Quality-preserving defaults: the tool keeps the source's look, not the reels spec.
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ]
        logger.info("ffmpeg cut %d segments -> %s", len(segments), out_path.name)
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise SegmentCutError("ffmpeg binary not found") from exc
        except subprocess.CalledProcessError as exc:
            raise SegmentCutError(f"ffmpeg failed: {exc.stderr.strip()[-500:]}") from exc
