"""FFmpeg implementation of the VideoEditor port (cut + reframe)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from reels.application.ports.video_editor import RenderSpec, VideoEditor
from reels.domain.reel.layout_plan import LayoutPlan, ReframeMode
from reels.domain.shared.value_objects import TimeRange

logger = logging.getLogger(__name__)


class FFmpegError(RuntimeError):
    """An ffmpeg invocation failed."""


class FFmpegVideoEditor(VideoEditor):
    def __init__(self, spec: RenderSpec, ffmpeg_path: str | None = None) -> None:
        self._spec = spec
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def cut(self, source_path: Path, time_range: TimeRange, out_path: Path) -> None:
        # -ss before -i seeks fast to the nearest keyframe; re-encoding then trims to the exact
        # start, giving an accurate cut without keyframe drift at the boundaries (spec §5.5).
        out_path.parent.mkdir(parents=True, exist_ok=True)
        args = [
            "-ss", f"{time_range.start:.3f}",
            "-i", str(source_path),
            "-t", f"{time_range.duration:.3f}",
            *self._encode_args(),
            str(out_path),
        ]
        self._run(args)

    def reframe(self, in_path: Path, layout: LayoutPlan, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        args = [
            "-i", str(in_path),
            "-vf", self._video_filter(layout),
            *self._encode_args(),
            str(out_path),
        ]
        self._run(args)

    def _video_filter(self, layout: LayoutPlan) -> str:
        res = self._spec.resolution
        if layout.mode is ReframeMode.PRESENTER_ONLY:
            c = layout.presenter_crop
            return f"crop={c.width}:{c.height}:{c.x}:{c.y},scale={res.width}:{res.height}"
        # MODE B (stacked slides + presenter) is a later slice.
        raise FFmpegError(f"reframe mode {layout.mode} is not implemented yet")

    def _encode_args(self) -> list[str]:
        spec = self._spec
        args = [
            "-c:v", spec.video_codec,
            "-b:v", spec.video_bitrate,
            "-pix_fmt", "yuv420p",
            "-c:a", spec.audio_codec,
            "-b:a", spec.audio_bitrate,
        ]
        if spec.faststart:
            args += ["-movflags", "+faststart"]
        return args

    def _run(self, args: list[str]) -> None:
        cmd = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args]
        logger.info("ffmpeg %s", " ".join(args))
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise FFmpegError("ffmpeg binary not found on PATH") from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(f"ffmpeg failed: {exc.stderr.strip()}") from exc
