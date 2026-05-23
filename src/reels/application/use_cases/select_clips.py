"""Select use case (spec §5.3): turn a transcript into validated, non-overlapping reel candidates.

The LLM proposes moments (text only); the domain reconciliation service then enforces the business
rules — duration window, in-bounds, word-boundary snapping, overlap removal — before they become
Reels. Selection is content-driven: zero clips is a valid outcome for a weak source.
"""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.domain.reel.clip_selector import ClipSelector, SelectionConstraints
from reels.domain.reel.reel import Reel
from reels.domain.services.clip_reconciliation import ClipReconciliationService
from reels.domain.shared.value_objects import TimeRange

_WARNING_PREFIX = "select: "


class CannotSelect(Exception):
    """Raised when selection cannot run (e.g. the video has not been transcribed)."""


@dataclass(slots=True)
class SelectClips:
    transcripts: TranscriptRepository
    selector: ClipSelector
    reconciliation: ClipReconciliationService
    manifests: ManifestRepository
    constraints: SelectionConstraints

    def execute(self, manifest: Manifest) -> Manifest:
        if manifest.transcript_path is None:
            raise CannotSelect(f"'{manifest.source.id}' has no transcript — run transcribe first")

        # Re-running select must be idempotent: drop this stage's prior reels and warnings up front
        # so they don't accumulate across runs (the manifest persists between runs).
        manifest.reels = []
        manifest.warnings = [w for w in manifest.warnings if not w.startswith(_WARNING_PREFIX)]

        transcript = self.transcripts.load(manifest.transcript_path)
        if not transcript.has_words():
            manifest.flag(f"{_WARNING_PREFIX}transcript has no word-level timings; cannot snap")

        candidates = self.selector.select_clips(transcript, self.constraints)
        result = self.reconciliation.reconcile(
            candidates,
            self.constraints,
            video_span=self._video_span(manifest, transcript.duration_seconds),
            snap_start=transcript.snap_start_to_word_boundary,
            snap_end=transcript.snap_end_to_word_boundary,
        )

        manifest.reels = [
            Reel(source_id=manifest.source.id.value, index=i + 1, candidate=candidate)
            for i, candidate in enumerate(result.accepted)
        ]
        for note in result.notes:
            manifest.flag(f"{_WARNING_PREFIX}{note}")
        manifest.mark_completed(Stage.SELECT)
        self.manifests.save(manifest)
        return manifest

    @staticmethod
    def _video_span(manifest: Manifest, transcript_duration: float) -> TimeRange:
        # ffprobe's duration is more authoritative than the transcriber's; prefer it when present.
        meta = manifest.source.metadata
        duration = meta.duration_seconds if meta else transcript_duration
        return TimeRange(start=0.0, end=max(duration, transcript_duration))
