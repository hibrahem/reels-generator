"""The SourceVideo aggregate root."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .video_metadata import VideoMetadata


@dataclass(frozen=True, slots=True)
class SourceVideoId:
    """Stable identity for a source video, derived from its filename stem.

    Used in output naming (``{source_name}__{NN}__{slug}.mp4``) and as the working-dir key.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("source video id cannot be empty")

    @classmethod
    def from_path(cls, path: Path) -> SourceVideoId:
        stem = path.stem
        safe = re.sub(r"[^\w.-]+", "_", stem, flags=re.UNICODE).strip("_")
        return cls(safe or "source")

    def __str__(self) -> str:
        return self.value


@dataclass(slots=True)
class SourceVideo:
    """Aggregate root for one long-form course video and its derived working state.

    Identity is :class:`SourceVideoId` (filename-derived), not structural equality. Metadata is
    populated by the ingest stage; until then it is ``None``.
    """

    id: SourceVideoId
    path: Path
    working_dir: Path
    metadata: VideoMetadata | None = None

    @classmethod
    def discovered_at(cls, path: Path, work_root: Path) -> SourceVideo:
        """Create a source video for a file found on disk, with its working dir resolved."""
        video_id = SourceVideoId.from_path(path)
        return cls(id=video_id, path=path, working_dir=work_root / video_id.value)

    def describe(self, metadata: VideoMetadata) -> None:
        """Record probed technical metadata (ingest stage)."""
        self.metadata = metadata

    @property
    def is_ingested(self) -> bool:
        return self.metadata is not None

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SourceVideo) and other.id == self.id

    def __hash__(self) -> int:
        return hash(self.id)
