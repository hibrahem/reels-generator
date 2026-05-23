"""Per-run options threaded into stage handlers (e.g. limiting which reels a stage processes)."""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.domain.reel.reel import Reel


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Options for a single pipeline run. Non-reel stages ignore these."""

    reel_indices: frozenset[int] | None = None  # if set, per-reel stages process only these indices


def selected_reels(manifest: Manifest, options: RunOptions | None) -> list[Reel]:
    """The reels a per-reel stage should process, honoring an optional --reel filter."""
    if options is not None and options.reel_indices is not None:
        return [r for r in manifest.reels if r.index in options.reel_indices]
    return list(manifest.reels)
