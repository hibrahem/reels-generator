"""FFmpeg implementation of the VideoEditor port (cut + reframe)."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from reels.application.ports.video_editor import LogoOverlay, RenderSpec, VideoEditor
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

    def brand(
        self,
        in_path,
        out_path,
        *,
        intro=None,
        outro=None,
        logo: LogoOverlay | None = None,
    ) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if intro is None and outro is None and logo is None:
            shutil.copyfile(in_path, out_path)  # already conformant; nothing to brand
            return
        if intro is None and outro is None:  # logo only — no concat needed
            self._brand_logo_only(in_path, logo, out_path)
            return
        self._brand_concat(in_path, intro, outro, logo, out_path)

    def _brand_logo_only(self, in_path, logo: LogoOverlay, out_path) -> None:
        lw = round(self._spec.resolution.width * logo.width_ratio)
        x, y = _overlay_xy(logo.position, self._spec.resolution.width)
        fc = (
            f"[1:v]format=rgba,colorchannelmixer=aa={logo.opacity},scale={lw}:-1[lg];"
            f"[0:v][lg]overlay={x}:{y}[v]"
        )
        self._run([
            "-i", str(in_path), "-i", str(logo.path),
            "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
            *self._encode_args(), str(out_path),
        ])

    def _brand_concat(self, in_path, intro, outro, logo, out_path) -> None:
        segments = [s for s in (intro, in_path, outro) if s is not None]
        main_index = segments.index(in_path)
        res = self._spec.resolution
        inputs: list[str] = []
        for seg in segments:
            inputs += ["-i", str(seg)]
        logo_index = None
        if logo is not None:
            logo_index = len(segments)
            inputs += ["-i", str(logo.path)]

        norm = (
            f"scale={res.width}:{res.height}:force_original_aspect_ratio=decrease,"
            f"pad={res.width}:{res.height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p"
        )
        parts: list[str] = []
        concat_labels = ""
        for i, _ in enumerate(segments):
            if i == main_index and logo is not None:
                lw = round(res.width * logo.width_ratio)
                x, y = _overlay_xy(logo.position, res.width)
                parts.append(f"[{i}:v]{norm}[m{i}]")
                parts.append(
                    f"[{logo_index}:v]format=rgba,colorchannelmixer=aa={logo.opacity},"
                    f"scale={lw}:-1[lg]"
                )
                parts.append(f"[m{i}][lg]overlay={x}:{y}[v{i}]")
            else:
                parts.append(f"[{i}:v]{norm}[v{i}]")
            parts.append(
                f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[a{i}]"
            )
            concat_labels += f"[v{i}][a{i}]"
        parts.append(f"{concat_labels}concat=n={len(segments)}:v=1:a=1[vout][aout]")
        self._run([
            *inputs, "-filter_complex", ";".join(parts),
            "-map", "[vout]", "-map", "[aout]",
            *self._encode_args(), str(out_path),
        ])

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


# Logo overlay position → (x, y) expressions using libass overlay variables; M is the edge margin.
def _overlay_xy(position: str, frame_width: int) -> tuple[str, str]:
    m = round(frame_width * 0.04)
    mapping = {
        "bottom-right": (f"main_w-overlay_w-{m}", f"main_h-overlay_h-{m}"),
        "bottom-left": (f"{m}", f"main_h-overlay_h-{m}"),
        "top-right": (f"main_w-overlay_w-{m}", f"{m}"),
        "top-left": (f"{m}", f"{m}"),
        "bottom-center": ("(main_w-overlay_w)/2", f"main_h-overlay_h-{m}"),
    }
    return mapping.get(position, mapping["bottom-right"])
