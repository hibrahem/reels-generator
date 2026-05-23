"""Filesystem implementation of :class:`SourceVideoRepository` — scans the input folder."""

from __future__ import annotations

from pathlib import Path

from reels.domain.source_video.repository import SourceVideoRepository
from reels.domain.source_video.source_video import SourceVideo

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"}


class FilesystemVideoLibrary(SourceVideoRepository):
    def __init__(self, input_dir: Path, work_root: Path) -> None:
        self._input_dir = input_dir
        self._work_root = work_root

    def discover(self) -> list[SourceVideo]:
        if not self._input_dir.exists():
            raise FileNotFoundError(f"input directory does not exist: {self._input_dir}")
        files = sorted(
            p
            for p in self._input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS
        )
        return [SourceVideo.discovered_at(path, self._work_root) for path in files]
