"""FFprobe-backed implementation of the :class:`VideoProber` port (spec §5.1)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from reels.domain.shared.value_objects import Resolution
from reels.domain.source_video.video_metadata import VideoMetadata
from reels.domain.source_video.video_prober import VideoProber


class FFprobeError(RuntimeError):
    """ffprobe failed or returned output that could not be parsed."""


class FFprobeVideoProber(VideoProber):
    def __init__(self, ffprobe_path: str | None = None) -> None:
        self._ffprobe = ffprobe_path or shutil.which("ffprobe") or "ffprobe"

    def probe(self, path: Path) -> VideoMetadata:
        payload = self._run(path)
        streams = payload.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if video is None:
            raise FFprobeError(f"no video stream found in {path}")

        return VideoMetadata(
            duration_seconds=self._duration(payload, video),
            resolution=Resolution(width=int(video["width"]), height=int(video["height"])),
            fps=self._fps(video),
            has_audio=audio is not None,
            video_codec=video.get("codec_name"),
            audio_codec=audio.get("codec_name") if audio else None,
        )

    def _run(self, path: Path) -> dict:
        cmd = [
            self._ffprobe,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise FFprobeError("ffprobe binary not found on PATH") from exc
        except subprocess.CalledProcessError as exc:
            raise FFprobeError(f"ffprobe failed for {path}: {exc.stderr.strip()}") from exc
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise FFprobeError(f"could not parse ffprobe output for {path}") from exc

    @staticmethod
    def _duration(payload: dict, video: dict) -> float:
        for source in (payload.get("format", {}).get("duration"), video.get("duration")):
            if source:
                try:
                    return float(source)
                except (TypeError, ValueError):
                    continue
        raise FFprobeError("could not determine video duration")

    @staticmethod
    def _fps(video: dict) -> float:
        rate = video.get("avg_frame_rate") or video.get("r_frame_rate") or "0/1"
        try:
            num, _, den = rate.partition("/")
            denominator = float(den) if den else 1.0
            return float(num) / denominator if denominator else 0.0
        except (TypeError, ValueError, ZeroDivisionError):
            return 0.0
