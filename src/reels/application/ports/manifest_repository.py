"""Port for persisting and loading per-video manifests."""

from __future__ import annotations

from abc import ABC, abstractmethod

from reels.application.manifest import Manifest


class ManifestRepository(ABC):
    """Reads and writes the per-video manifest (JSON on disk in the working dir)."""

    @abstractmethod
    def load(self, source_id: str) -> Manifest | None:
        """Return the stored manifest for a source, or ``None`` if it has never been ingested."""
        raise NotImplementedError

    @abstractmethod
    def save(self, manifest: Manifest) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Manifest]:
        """Return every persisted manifest (used when resuming a run via ``--from``)."""
        raise NotImplementedError
