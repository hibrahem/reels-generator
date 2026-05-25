"""Tests for the EditTranscript use case (ticket #20): word-level edits preserve timings."""

from __future__ import annotations

from pathlib import Path

import pytest

from reels.application.manifest import Manifest
from reels.application.use_cases.edit_transcript import (
    EditTranscript,
    TranscriptNotAvailable,
    TranscriptStructureChanged,
)
from reels.domain.shared.value_objects import Resolution
from reels.domain.source_video.source_video import SourceVideo, SourceVideoId
from reels.domain.source_video.video_metadata import VideoMetadata
from reels.domain.transcript.transcript import Segment, Transcript, Word
from reels.infrastructure.persistence.json_transcript_repository import (
    JsonTranscriptRepository,
)


def _transcript() -> Transcript:
    words = (
        Word("هذا", 0.0, 0.4, 0.99),
        Word("نص", 0.4, 0.8, 0.95),
        Word("تجريبي", 0.8, 1.5, 0.90),
    )
    return Transcript(
        source_id="s",
        language="ar",
        duration_seconds=2.0,
        segments=(Segment("هذا نص تجريبي", 0.0, 1.5, words),),
    )


def _manifest(working_dir: Path, transcript_path: Path | None) -> Manifest:
    src = SourceVideo(
        id=SourceVideoId("s"),
        path=working_dir / "s.mov",
        working_dir=working_dir,
        metadata=VideoMetadata(2.0, Resolution(1920, 1080), 30.0, True),
    )
    return Manifest(source=src, transcript_path=transcript_path)


def _edited_segments(new_texts: list[str], src: Transcript) -> list[Segment]:
    """Build edited segments that change only word text, keeping every timing."""
    seg = src.segments[0]
    words = tuple(
        Word(text, w.start, w.end, w.probability)
        for text, w in zip(new_texts, seg.words, strict=True)
    )
    return [Segment(" ".join(new_texts), seg.start, seg.end, words)]


def test_edit_word_text_preserves_timings_and_persists(tmp_path: Path) -> None:
    repo = JsonTranscriptRepository()
    repo.save(_transcript(), tmp_path)
    manifest = _manifest(tmp_path, tmp_path / "transcript.json")

    edited = EditTranscript(transcripts=repo).execute(
        manifest, _edited_segments(["ذلك", "النص", "المصحح"], _transcript())
    )

    # Text changed, timings identical.
    words = edited.segments[0].words
    assert [w.text for w in words] == ["ذلك", "النص", "المصحح"]
    assert [(w.start, w.end) for w in words] == [(0.0, 0.4), (0.4, 0.8), (0.8, 1.5)]

    # And it was actually written to disk (next caption render reads this).
    reloaded = repo.load(manifest.transcript_path)
    assert [w.text for w in reloaded.segments[0].words] == ["ذلك", "النص", "المصحح"]
    assert [(w.start, w.end) for w in reloaded.segments[0].words] == [
        (0.0, 0.4),
        (0.4, 0.8),
        (0.8, 1.5),
    ]


def test_edit_without_transcript_raises(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, transcript_path=None)
    with pytest.raises(TranscriptNotAvailable):
        EditTranscript(transcripts=JsonTranscriptRepository()).execute(manifest, [])


def test_changing_word_timing_is_rejected(tmp_path: Path) -> None:
    repo = JsonTranscriptRepository()
    repo.save(_transcript(), tmp_path)
    manifest = _manifest(tmp_path, tmp_path / "transcript.json")

    tampered = [
        Segment(
            "هذا نص تجريبي",
            0.0,
            1.5,
            (
                Word("هذا", 0.0, 0.4),
                Word("نص", 0.4, 0.9),  # end nudged 0.8 -> 0.9
                Word("تجريبي", 0.9, 1.5),
            ),
        )
    ]
    with pytest.raises(TranscriptStructureChanged):
        EditTranscript(transcripts=repo).execute(manifest, tampered)


def test_changing_word_count_is_rejected(tmp_path: Path) -> None:
    repo = JsonTranscriptRepository()
    repo.save(_transcript(), tmp_path)
    manifest = _manifest(tmp_path, tmp_path / "transcript.json")

    too_few = [Segment("هذا نص", 0.0, 1.5, (Word("هذا", 0.0, 0.4), Word("نص", 0.4, 0.8)))]
    with pytest.raises(TranscriptStructureChanged):
        EditTranscript(transcripts=repo).execute(manifest, too_few)


def test_changing_segment_count_is_rejected(tmp_path: Path) -> None:
    repo = JsonTranscriptRepository()
    repo.save(_transcript(), tmp_path)
    manifest = _manifest(tmp_path, tmp_path / "transcript.json")

    split = [
        Segment("هذا", 0.0, 0.4, (Word("هذا", 0.0, 0.4),)),
        Segment("نص تجريبي", 0.4, 1.5, (Word("نص", 0.4, 0.8), Word("تجريبي", 0.8, 1.5))),
    ]
    with pytest.raises(TranscriptStructureChanged):
        EditTranscript(transcripts=repo).execute(manifest, split)
