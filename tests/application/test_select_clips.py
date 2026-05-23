"""SelectClips use case test with fake adapters — no network, exercises reconciliation wiring."""

from pathlib import Path

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.application.use_cases.select_clips import SelectClips
from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.clip_selector import ClipSelector, SelectionConstraints
from reels.domain.services.clip_reconciliation import ClipReconciliationService
from reels.domain.shared.value_objects import Confidence, Resolution, TimeRange
from reels.domain.source_video.source_video import SourceVideo, SourceVideoId
from reels.domain.source_video.video_metadata import VideoMetadata
from reels.domain.transcript.transcript import Segment, Transcript, Word


def _transcript() -> Transcript:
    # One word per second across the video so word-boundary snapping resolves to integers.
    words = tuple(Word(text=str(i), start=float(i), end=float(i) + 0.5) for i in range(300))
    seg = Segment(text="...", start=0.0, end=300.0, words=words)
    return Transcript(source_id="src", language="ar", duration_seconds=300.0, segments=(seg,))


def _candidate(start, end, title, conf) -> ClipCandidate:
    return ClipCandidate(
        time_range=TimeRange(start, end),
        title=title,
        hook="h",
        caption="c",
        reason="r",
        confidence=Confidence(conf),
    )


class FakeSelector(ClipSelector):
    def __init__(self, clips):
        self._clips = clips

    def select_clips(self, transcript, constraints):
        return self._clips


class FakeTranscripts(TranscriptRepository):
    def __init__(self, transcript):
        self._t = transcript

    def save(self, transcript, working_dir):
        return Path("unused")

    def load(self, path):
        return self._t


class FakeManifests(ManifestRepository):
    def __init__(self):
        self.saved = None

    def load(self, source_id):
        return None

    def save(self, manifest):
        self.saved = manifest

    def list_all(self):
        return []


def _manifest() -> Manifest:
    source = SourceVideo(
        id=SourceVideoId("src"),
        path=Path("src.mov"),
        working_dir=Path("work/src"),
        metadata=VideoMetadata(
            duration_seconds=300.0, resolution=Resolution(1920, 1080), fps=30.0, has_audio=True
        ),
    )
    return Manifest(source=source, transcript_path=Path("work/src/transcript.json"))


def _use_case(clips) -> SelectClips:
    return SelectClips(
        transcripts=FakeTranscripts(_transcript()),
        selector=FakeSelector(clips),
        reconciliation=ClipReconciliationService(),
        manifests=FakeManifests(),
        constraints=SelectionConstraints(min_clip_seconds=20, max_clip_seconds=90),
    )


def test_builds_reels_and_drops_overlap():
    clips = [
        _candidate(10, 40, "A", 0.9),  # good
        _candidate(35, 70, "B", 0.5),  # overlaps A, lower confidence → dropped
        _candidate(100, 140, "C", 0.8),  # good
    ]
    manifest = _use_case(clips).execute(_manifest())
    titles = [r.candidate.title for r in manifest.reels]
    assert titles == ["A", "C"]
    assert [r.index for r in manifest.reels] == [1, 2]
    assert manifest.is_completed(Stage.SELECT)


def test_zero_clips_is_valid():
    manifest = _use_case([]).execute(_manifest())
    assert manifest.reels == []
    assert manifest.is_completed(Stage.SELECT)


def test_output_filename_scheme():
    manifest = _use_case([_candidate(10, 40, "Domain Coupling!", 0.9)]).execute(_manifest())
    name = manifest.reels[0].output_filename()
    assert name.startswith("src__01__")
    assert name.endswith(".mp4")
