"""Port for inspecting the host media toolchain (FFmpeg/FFprobe and their capabilities)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MediaToolchainStatus:
    """What the host's FFmpeg can do — drives fail-fast checks per stage."""

    ffmpeg_path: str | None
    ffprobe_path: str | None
    has_libass: bool
    has_videotoolbox: bool
    version: str | None

    @property
    def is_present(self) -> bool:
        return self.ffmpeg_path is not None and self.ffprobe_path is not None


class MediaEnvironment(ABC):
    """Probes the host for FFmpeg/FFprobe availability and subtitle (libass) support."""

    @abstractmethod
    def status(self) -> MediaToolchainStatus:
        raise NotImplementedError
