from pathlib import Path

from reels.application.manifest import Manifest
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.application.use_cases.reel_editing import DeleteReel, EditReel
from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.reel import Reel
from reels.domain.shared.value_objects import Confidence, Resolution, TimeRange
from reels.domain.source_video.source_video import SourceVideo, SourceVideoId
from reels.domain.source_video.video_metadata import VideoMetadata
from reels.domain.transcript.transcript import Segment, Transcript, Word


class FakeManifests(ManifestRepository):
    def __init__(self):
        self.saved = None

    def load(self, source_id):
        return None

    def save(self, manifest):
        self.saved = manifest

    def list_all(self):
        return []


class FakeTranscripts(TranscriptRepository):
    def save(self, transcript, working_dir):
        return Path("x")

    def load(self, path):
        words = tuple(Word(str(i), float(i), float(i) + 0.5) for i in range(300))
        return Transcript("s", "ar", 300.0, (Segment("...", 0.0, 300.0, words),))


def _reel(index, start, end, title="t") -> Reel:
    c = ClipCandidate(TimeRange(start, end), title, "hook", "cap", "r", Confidence(0.9))
    r = Reel(source_id="s", index=index, candidate=c)
    r.reframed_path = Path("reframed.mp4")  # pretend it was rendered
    return r


def _manifest() -> Manifest:
    src = SourceVideo(
        id=SourceVideoId("s"),
        path=Path("s.mov"),
        working_dir=Path("work/s"),
        metadata=VideoMetadata(300.0, Resolution(1920, 1080), 30.0, True),
    )
    m = Manifest(source=src, transcript_path=Path("work/s/transcript.json"))
    m.reels = [_reel(1, 10, 40), _reel(2, 100, 140)]
    return m


def test_edit_metadata_only_keeps_renders():
    m = _manifest()
    EditReel(FakeManifests(), FakeTranscripts()).execute(m, 1, title="New Title", hook="hi")
    reel = m.reels[0]
    assert reel.candidate.title == "New Title"
    assert reel.candidate.hook == "hi"
    assert reel.reframed_path is not None  # unchanged time → renders preserved


def test_edit_time_resnaps_and_clears_renders():
    m = _manifest()
    EditReel(FakeManifests(), FakeTranscripts()).execute(m, 1, start=12.3, end=45.7)
    reel = m.reels[0]
    # snapped to integer word boundaries from the fake transcript
    assert reel.candidate.time_range.start == 13.0
    assert reel.reframed_path is None  # renders invalidated


def test_delete_removes_reel_keeps_others():
    m = _manifest()
    DeleteReel(FakeManifests()).execute(m, 1)
    assert [r.index for r in m.reels] == [2]
