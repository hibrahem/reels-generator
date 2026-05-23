"""Port for discovering source videos. Implemented by infrastructure (filesystem scanner)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .source_video import SourceVideo


class SourceVideoRepository(ABC):
    """Discovers the source videos available for processing.

    The domain depends on this interface; the concrete filesystem implementation lives in
    infrastructure, keeping the dependency rule intact.
    """

    @abstractmethod
    def discover(self) -> list[SourceVideo]:
        """Return every source video found in the configured input location, ingest-ready."""
        raise NotImplementedError
