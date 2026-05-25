"""Edit transcript text use case (ticket #20): word-level edits that preserve timings.

A creator corrects misheard words without re-running transcription. We edit the *text* of each
word in place and keep every word's start/end so the burned-in caption karaoke/active-word timing
stays intact. The edited transcript replaces the persisted one; the next caption render consumes it.

Clean Architecture: this orchestrates the domain Transcript + the persistence port. It rejects any
edit that would change the word-level structure or timings (count, order, or start/end), so the
"preserve timings" invariant lives here rather than being trusted from the API boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.domain.transcript.transcript import Segment, Transcript, Word


class TranscriptNotAvailable(Exception):
    """The video has no persisted transcript to edit (transcribe was never run)."""


class TranscriptStructureChanged(Exception):
    """An edit would change word-level structure or timings, which this use case forbids.

    Word-level editing preserves each word's start/end and the segment/word counts; only the
    *text* of words (and the convenience segment text) may change. Anything else means the caller
    is trying to do something this endpoint is not for (re-segmentation, re-timing, insert/delete).
    """


@dataclass(slots=True)
class EditTranscript:
    """Replaces a video's transcript text word-by-word while preserving every word's timing."""

    transcripts: TranscriptRepository

    def execute(self, manifest: Manifest, segments: list[Segment]) -> Transcript:
        if manifest.transcript_path is None:
            raise TranscriptNotAvailable(
                f"'{manifest.source.id}' has no transcript — run transcribe first"
            )

        existing = self.transcripts.load(manifest.transcript_path)
        self._assert_timings_preserved(existing.segments, tuple(segments))

        edited = Transcript(
            source_id=existing.source_id,
            language=existing.language,
            duration_seconds=existing.duration_seconds,
            segments=tuple(segments),
        )
        manifest.transcript_path = self.transcripts.save(edited, manifest.source.working_dir)
        return edited

    @staticmethod
    def _assert_timings_preserved(
        existing: tuple[Segment, ...], edited: tuple[Segment, ...]
    ) -> None:
        if len(existing) != len(edited):
            raise TranscriptStructureChanged(
                f"segment count changed: {len(existing)} → {len(edited)}"
            )
        for i, (old_seg, new_seg) in enumerate(zip(existing, edited, strict=True)):
            if (old_seg.start, old_seg.end) != (new_seg.start, new_seg.end):
                raise TranscriptStructureChanged(f"segment {i} timing changed")
            if len(old_seg.words) != len(new_seg.words):
                raise TranscriptStructureChanged(
                    f"segment {i} word count changed: "
                    f"{len(old_seg.words)} → {len(new_seg.words)}"
                )
            for j, (old_word, new_word) in enumerate(
                zip(old_seg.words, new_seg.words, strict=True)
            ):
                _assert_word_timing(i, j, old_word, new_word)


def _assert_word_timing(seg_i: int, word_j: int, old: Word, new: Word) -> None:
    if (old.start, old.end) != (new.start, new.end):
        raise TranscriptStructureChanged(
            f"segment {seg_i} word {word_j} timing changed — timings must be preserved"
        )
