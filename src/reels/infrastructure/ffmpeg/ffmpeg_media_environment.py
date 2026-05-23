"""Probes host FFmpeg/FFprobe capabilities (notably libass). Implements MediaEnvironment."""

from __future__ import annotations

import shutil
import subprocess

from reels.application.ports.media_environment import MediaEnvironment, MediaToolchainStatus


class FFmpegMediaEnvironment(MediaEnvironment):
    def __init__(self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None) -> None:
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg")
        self._ffprobe = ffprobe_path or shutil.which("ffprobe")

    def status(self) -> MediaToolchainStatus:
        version = self._version()
        buildconf = self._buildconf()
        filters = self._filters()
        # libass burn-in needs both the demuxer/filter and the library compiled in.
        has_libass = "--enable-libass" in buildconf or "libass" in buildconf
        has_subtitles_filter = " ass " in f" {filters} " or " subtitles " in f" {filters} "
        return MediaToolchainStatus(
            ffmpeg_path=self._ffmpeg,
            ffprobe_path=self._ffprobe,
            has_libass=has_libass and has_subtitles_filter,
            has_videotoolbox="--enable-videotoolbox" in buildconf,
            version=version,
        )

    def _version(self) -> str | None:
        out = self._capture([self._ffmpeg, "-hide_banner", "-version"]) if self._ffmpeg else ""
        return out.splitlines()[0] if out else None

    def _buildconf(self) -> str:
        if not self._ffmpeg:
            return ""
        return self._capture([self._ffmpeg, "-hide_banner", "-buildconf"])

    def _filters(self) -> str:
        if not self._ffmpeg:
            return ""
        return self._capture([self._ffmpeg, "-hide_banner", "-filters"])

    @staticmethod
    def _capture(cmd: list[str]) -> str:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return f"{result.stdout}\n{result.stderr}"
        except (FileNotFoundError, OSError):
            return ""
