from reels.infrastructure.ffmpeg.ffmpeg_video_editor import (
    _derive_ffprobe,
    _ending_sound_filtergraph,
)


def test_delay_aligns_sound_end_to_clip_end():
    # 30s clip, 3s sound → sound starts at 27s so its tail lands on the clip end.
    fc = _ending_sound_filtergraph(main_dur=30.0, sound_dur=3.0, volume=0.7)
    assert "adelay=27000|27000" in fc
    assert "volume=0.7" in fc
    assert "normalize=0" in fc  # keep speech at full level, no per-input halving
    assert "amix=inputs=2" in fc
    assert "duration=first" in fc  # output trimmed to the clip length


def test_delay_clamps_when_sound_longer_than_clip():
    # 5s sound over a 2s clip → start at 0 (sound trimmed to the clip by duration=first).
    fc = _ending_sound_filtergraph(main_dur=2.0, sound_dur=5.0, volume=0.7)
    assert "adelay=0|0" in fc


def test_delay_rounds_to_milliseconds():
    fc = _ending_sound_filtergraph(main_dur=10.0, sound_dur=2.5, volume=0.7)
    assert "adelay=7500|7500" in fc


def test_derive_ffprobe_prefers_sibling(tmp_path):
    (tmp_path / "ffmpeg").write_text("")
    probe = tmp_path / "ffprobe"
    probe.write_text("")
    assert _derive_ffprobe(str(tmp_path / "ffmpeg")) == str(probe)


def test_derive_ffprobe_falls_back_when_no_sibling(tmp_path):
    # No sibling ffprobe on disk → falls back to PATH ("ffprobe" or an absolute path to it).
    assert _derive_ffprobe(str(tmp_path / "ffmpeg")).endswith("ffprobe")
