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

# Mix level for the ending sound, on top of the (unchanged) speech. No ducking — see AgDR-0003.
ENDING_SOUND_VOLUME = 0.7


class FFmpegError(RuntimeError):
    """An ffmpeg invocation failed."""


class FFmpegVideoEditor(VideoEditor):
    def __init__(self, spec: RenderSpec, ffmpeg_path: str | None = None) -> None:
        self._spec = spec
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"
        self._ffprobe = _derive_ffprobe(self._ffmpeg)

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
        ending_sound=None,
    ) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Mix the ending sound into the main clip's tail first — orthogonal to intro/outro/logo,
        # so every branding combination below works against the mixed clip (AgDR-0003).
        main = in_path
        tmp: Path | None = None
        if ending_sound is not None:
            tmp = out_path.parent / f".{out_path.stem}__endsound.mp4"
            self._mix_ending_sound(in_path, ending_sound, tmp)
            main = tmp
        try:
            if intro is None and outro is None and logo is None:
                shutil.copyfile(main, out_path)  # already conformant; nothing more to brand
            elif intro is None and outro is None:  # logo only — no concat needed
                self._brand_logo_only(main, logo, out_path)
            else:
                self._brand_concat(main, intro, outro, logo, out_path)
        finally:
            if tmp is not None and tmp.exists():
                tmp.unlink()

    def _mix_ending_sound(self, main: Path, sound: Path, out_path: Path) -> None:
        """Mix ``sound`` into ``main``'s tail so it ends as the main clip ends (AgDR-0003).

        Video is stream-copied; only the audio is re-encoded.
        """
        fc = _ending_sound_filtergraph(
            self._probe_duration(main), self._probe_duration(sound), ENDING_SOUND_VOLUME
        )
        spec = self._spec
        self._run([
            "-i", str(main), "-i", str(sound),
            "-filter_complex", fc,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", spec.audio_codec, "-b:a", spec.audio_bitrate,
            str(out_path),
        ])

    def _probe_duration(self, path: Path) -> float:
        cmd = [
            self._ffprobe, "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise FFmpegError("ffprobe binary not found") from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(f"ffprobe failed: {exc.stderr.strip()}") from exc
        try:
            return float(out.stdout.strip())
        except ValueError as exc:
            raise FFmpegError(f"ffprobe returned no duration for {path}") from exc

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


def _derive_ffprobe(ffmpeg: str) -> str:
    """Locate ffprobe next to the configured ffmpeg binary, else fall back to PATH."""
    p = Path(ffmpeg)
    if "ffmpeg" in p.name:
        cand = p.with_name(p.name.replace("ffmpeg", "ffprobe"))
        if cand.exists():
            return str(cand)
    return shutil.which("ffprobe") or "ffprobe"


def _ending_sound_filtergraph(main_dur: float, sound_dur: float, volume: float) -> str:
    """filter_complex mixing the ending sound into the main clip's tail, ending-aligned.

    The sound starts at ``main_dur - sound_dur`` (clamped to 0 when the sound is longer than the
    clip) so its tail lands on the main clip's end. ``normalize=0`` keeps the speech at full level
    instead of amix's default per-input halving; ``duration=first`` trims the output to the main
    clip's length. See AgDR-0003.
    """
    delay_ms = max(0, round((main_dur - sound_dur) * 1000))
    stereo = "aformat=sample_fmts=fltp:channel_layouts=stereo"
    return (
        f"[0:a]aresample=48000,{stereo}[a0];"
        f"[1:a]aresample=48000,{stereo},volume={volume},adelay={delay_ms}|{delay_ms}[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
    )


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
