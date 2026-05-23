"""Use cases for editing a selected reel: trim/split its span and edit its metadata, or delete it.

Editing the span re-snaps to word boundaries and clears the reel's downstream artifacts so the
later stages re-render cleanly. The manifest stays the source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.reel import Reel
from reels.domain.shared.value_objects import TimeRange


class ReelNotFound(Exception):
    """The requested reel index does not exist on the manifest."""


def _find(manifest: Manifest, index: int) -> Reel:
    reel = next((r for r in manifest.reels if r.index == index), None)
    if reel is None:
        raise ReelNotFound(f"reel {index} not found")
    return reel


@dataclass(slots=True)
class EditReel:
    manifests: ManifestRepository
    transcripts: TranscriptRepository

    def execute(
        self,
        manifest: Manifest,
        index: int,
        *,
        start: float | None = None,
        end: float | None = None,
        title: str | None = None,
        hook: str | None = None,
        caption: str | None = None,
    ) -> Manifest:
        reel = _find(manifest, index)
        old = reel.candidate
        new_start = old.time_range.start if start is None else start
        new_end = old.time_range.end if end is None else end
        time_changed = (new_start, new_end) != (old.time_range.start, old.time_range.end)

        if time_changed and manifest.transcript_path is not None:
            transcript = self.transcripts.load(manifest.transcript_path)
            if transcript.has_words():
                new_start = transcript.snap_start_to_word_boundary(new_start)
                new_end = transcript.snap_end_to_word_boundary(new_end)

        reel.candidate = ClipCandidate(
            time_range=TimeRange(start=new_start, end=new_end),
            title=title if title is not None else old.title,
            hook=hook if hook is not None else old.hook,
            caption=caption if caption is not None else old.caption,
            reason=old.reason,
            confidence=old.confidence,
            visual_dependent=old.visual_dependent,
        )
        if time_changed:
            # Span moved → geometry, cut, and renders are stale; force re-render of this reel.
            reel.layout = None
            reel.cut_path = None
            reel.reframed_path = None
            reel.captioned_path = None
            reel.final_path = None
            reel.warnings = []

        self.manifests.save(manifest)
        return manifest


@dataclass(slots=True)
class DeleteReel:
    manifests: ManifestRepository

    def execute(self, manifest: Manifest, index: int) -> Manifest:
        if not any(r.index == index for r in manifest.reels):
            raise ReelNotFound(f"reel {index} not found")
        # Keep remaining indices stable (filenames are {source}__NN__slug); leave a gap.
        manifest.reels = [r for r in manifest.reels if r.index != index]
        self.manifests.save(manifest)
        return manifest
