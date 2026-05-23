"""Port for writing the per-source metadata sidecars (reels.json + reels.md) — spec §5.9."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SidecarEntry:
    """One finished reel's metadata, as recorded in the sidecar."""

    filename: str
    start: float
    end: float
    title: str
    hook: str
    caption: str
    mode: str
    confidence: float


class SidecarWriter(ABC):
    @abstractmethod
    def write(
        self, source_id: str, entries: list[SidecarEntry], output_dir: Path
    ) -> tuple[Path, Path]:
        """Write the JSON and Markdown sidecars; return their paths."""
        raise NotImplementedError
