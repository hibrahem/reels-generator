"""libass-based implementation of the CaptionRenderer port.

Writes an .ass next to the output, then burns it in with the (libass-enabled) ffmpeg using a font
directory so the configured Arabic font is found regardless of system fonts.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from reels.application.ports.caption_renderer import CaptionLine, CaptionRenderer
from reels.application.ports.video_editor import RenderSpec

from .ass_subtitle_builder import CaptionStyle, build_ass

logger = logging.getLogger(__name__)


class CaptionRenderError(RuntimeError):
    """Burning captions in failed."""


class LibassCaptionRenderer(CaptionRenderer):
    def __init__(
        self,
        style: CaptionStyle,
        fonts_dir: Path,
        spec: RenderSpec,
        ffmpeg_path: str | None = None,
    ) -> None:
        self._style = style
        self._fonts_dir = fonts_dir
        self._spec = spec
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def burn_in(self, video_in: Path, lines: list[CaptionLine], out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ass_path = out_path.with_suffix(".ass")
        ass_path.write_text(build_ass(lines, self._style), encoding="utf-8")

        vf = f"subtitles={_escape(ass_path)}:fontsdir={_escape(self._fonts_dir)}"
        cmd = [
            self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_in),
            "-vf", vf,
            "-c:v", self._spec.video_codec,
            "-b:v", self._spec.video_bitrate,
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
        ]
        if self._spec.faststart:
            cmd += ["-movflags", "+faststart"]
        cmd.append(str(out_path))

        logger.info("burning captions: %s", out_path.name)
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise CaptionRenderError(f"ffmpeg not found at {self._ffmpeg}") from exc
        except subprocess.CalledProcessError as exc:
            raise CaptionRenderError(f"caption burn-in failed: {exc.stderr.strip()}") from exc


def _escape(path: Path) -> str:
    # Escape characters special to ffmpeg's filtergraph option parser.
    return str(path).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
