"""Generate a browser-friendly preview proxy of a source video.

Sources may be .mov with PCM audio (great in Safari, silent in Chrome). This makes a 720p H.264 +
AAC, faststart proxy — hardware-encoded via VideoToolbox so it's quick — for reliable in-browser
playback with sound.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path


def build_preview(
    src: Path,
    out: Path,
    ffmpeg_path: str | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"
    if on_progress:
        on_progress("encoding 720p H.264 + AAC preview…")
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-vf", "scale=-2:720",
        "-c:v", "h264_videotoolbox", "-b:v", "2500k",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(out),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"preview encode failed: {exc.stderr.strip()}") from exc
    return out


def build_poster(src: Path, out: Path, at_seconds: float, ffmpeg_path: str | None = None) -> Path:
    """Extract a single downscaled poster frame for a library thumbnail."""
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{max(at_seconds, 0):.2f}", "-i", str(src),
        "-frames:v", "1", "-vf", "scale=640:-2", str(out),
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"poster extract failed: {exc.stderr.strip()}") from exc
    return out
