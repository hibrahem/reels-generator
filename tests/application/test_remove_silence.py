"""RemoveSilence use case orchestration, with fake ports (no ffmpeg)."""

from pathlib import Path

import pytest

from reels.application.ports.segment_cutter import SegmentCutter
from reels.application.ports.silence_detector import SilenceDetector
from reels.application.use_cases.remove_silence import (
    NoAudioTrack,
    RemoveSilence,
    SilenceRemovalSettings,
)
from reels.domain.shared.value_objects import Resolution, TimeRange
from reels.domain.source_video.video_metadata import VideoMetadata
from reels.domain.source_video.video_prober import VideoProber


class FakeProber(VideoProber):
    def __init__(self, duration: float = 10.0, has_audio: bool = True) -> None:
        self._duration = duration
        self._has_audio = has_audio

    def probe(self, path: Path) -> VideoMetadata:
        return VideoMetadata(
            duration_seconds=self._duration,
            resolution=Resolution(640, 480),
            fps=30.0,
            has_audio=self._has_audio,
            video_codec="h264",
            audio_codec="aac" if self._has_audio else None,
        )


class FakeDetector(SilenceDetector):
    def __init__(self, silences: list[TimeRange]) -> None:
        self._silences = silences

    def detect(self, video_path, *, threshold_db, min_silence, duration):
        return self._silences


class FakeCutter(SegmentCutter):
    def __init__(self) -> None:
        self.calls: list[tuple[Path, tuple, Path]] = []

    def cut(self, video_path, segments, out_path):
        self.calls.append((video_path, tuple(segments), out_path))
        out_path.write_bytes(b"trimmed")


def _use_case(prober=None, detector=None, cutter=None):
    return RemoveSilence(
        prober=prober or FakeProber(),
        detector=detector or FakeDetector([]),
        cutter=cutter or FakeCutter(),
    )


def test_video_without_audio_cannot_have_silence_removed(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    with pytest.raises(NoAudioTrack):
        _use_case(prober=FakeProber(has_audio=False)).execute(src, tmp_path / "out.mp4")


def test_silences_are_cut_and_result_reports_durations(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    out = tmp_path / "out.mp4"
    cutter = FakeCutter()
    result = _use_case(
        detector=FakeDetector([TimeRange(4.0, 6.0)]), cutter=cutter
    ).execute(src, out, SilenceRemovalSettings(padding=0.15))

    assert len(cutter.calls) == 1
    _, segments, _ = cutter.calls[0]
    assert [(round(s.start, 3), round(s.end, 3)) for s in segments] == [
        (0.0, 4.15),
        (5.85, 10.0),
    ]
    assert result.original_duration == pytest.approx(10.0)
    assert result.output_duration == pytest.approx(8.3)
    assert result.cuts_removed == 1


def test_video_with_no_silence_is_copied_unchanged(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"original-bytes")
    out = tmp_path / "out.mp4"
    cutter = FakeCutter()
    result = _use_case(detector=FakeDetector([]), cutter=cutter).execute(src, out)

    assert cutter.calls == []
    assert out.read_bytes() == b"original-bytes"
    assert result.cuts_removed == 0
    assert result.output_duration == pytest.approx(result.original_duration)


def test_progress_stages_are_emitted_in_order(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    stages: list[str] = []
    _use_case(detector=FakeDetector([TimeRange(4.0, 6.0)])).execute(
        src, tmp_path / "out.mp4", on_progress=lambda stage, msg: stages.append(stage)
    )
    assert stages == ["probe", "detect", "cut"]
