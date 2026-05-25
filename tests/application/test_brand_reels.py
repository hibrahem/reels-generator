from pathlib import Path

import pytest

from reels.application.manifest import Manifest
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.video_editor import VideoEditor
from reels.application.use_cases.brand_reels import BrandReels, CannotBrand
from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.reel import Reel
from reels.domain.shared.value_objects import Confidence, Resolution, TimeRange
from reels.domain.source_video.source_video import SourceVideo, SourceVideoId
from reels.domain.source_video.video_metadata import VideoMetadata


class FakeManifests(ManifestRepository):
    def __init__(self):
        self.saved = None

    def load(self, source_id):
        return None

    def save(self, manifest):
        self.saved = manifest

    def list_all(self):
        return []


class RecordingEditor(VideoEditor):
    """Captures the kwargs passed to brand() so we can assert the wiring."""

    def __init__(self):
        self.calls: list[dict] = []

    def cut(self, *a, **k):  # pragma: no cover - unused here
        ...

    def reframe(self, *a, **k):  # pragma: no cover - unused here
        ...

    def brand(self, in_path, out_path, *, intro=None, outro=None, logo=None, ending_sound=None):
        self.calls.append(
            {"intro": intro, "outro": outro, "logo": logo, "ending_sound": ending_sound}
        )


def _reel(index: int) -> Reel:
    c = ClipCandidate(TimeRange(10, 40), "t", "hook", "cap", "r", Confidence(0.9))
    r = Reel(source_id="s", index=index, candidate=c)
    r.captioned_path = Path(f"captioned_{index}.mp4")  # pretend caption ran
    return r


def _manifest() -> Manifest:
    src = SourceVideo(
        id=SourceVideoId("s"),
        path=Path("s.mov"),
        working_dir=Path("work/s"),
        metadata=VideoMetadata(300.0, Resolution(1920, 1080), 30.0, True),
    )
    m = Manifest(source=src)
    m.reels = [_reel(1), _reel(2)]
    return m


def test_brand_forwards_ending_sound_for_each_reel():
    editor = RecordingEditor()
    brand = BrandReels(
        editor=editor,
        manifests=FakeManifests(),
        outro=Path("assets/outro.mp4"),
        ending_sound=Path("assets/sting.mp3"),
    )
    brand.execute(_manifest())
    assert len(editor.calls) == 2
    assert all(c["ending_sound"] == Path("assets/sting.mp3") for c in editor.calls)
    assert all(c["outro"] == Path("assets/outro.mp4") for c in editor.calls)


def test_brand_ending_sound_defaults_to_none():
    editor = RecordingEditor()
    BrandReels(editor=editor, manifests=FakeManifests()).execute(_manifest())
    assert all(c["ending_sound"] is None for c in editor.calls)


def test_brand_requires_captioned_clip():
    m = _manifest()
    m.reels[0].captioned_path = None
    with pytest.raises(CannotBrand):
        BrandReels(editor=RecordingEditor(), manifests=FakeManifests()).execute(m)
