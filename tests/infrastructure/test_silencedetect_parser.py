"""Parsing ffmpeg silencedetect stderr output."""

from reels.infrastructure.ffmpeg.ffmpeg_silence_detector import parse_silencedetect

# Captured shape of real ffmpeg output: detection lines are interleaved with
# progress/config noise, and values carry varying precision.
SAMPLE = """\
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'input.mp4':
  Duration: 00:00:20.02, start: 0.000000, bitrate: 5157 kb/s
Stream mapping:
  Stream #0:1 -> #0:0 (aac (native) -> pcm_s16le (native))
[silencedetect @ 0x600002a30000] silence_start: 4.51102
[silencedetect @ 0x600002a30000] silence_end: 6.8004 | silence_duration: 2.28938
size=N/A time=00:00:10.00 bitrate=N/A speed= 500x
[silencedetect @ 0x600002a30000] silence_start: 12
[silencedetect @ 0x600002a30000] silence_end: 13.75 | silence_duration: 1.75
size=N/A time=00:00:20.02 bitrate=N/A speed= 480x
"""


def test_parses_start_end_pairs_from_noisy_stderr():
    intervals = parse_silencedetect(SAMPLE, duration=20.02)
    assert [(round(i.start, 3), round(i.end, 3)) for i in intervals] == [
        (4.511, 6.8),
        (12.0, 13.75),
    ]


def test_trailing_silence_without_end_line_runs_to_file_end():
    stderr = "[silencedetect @ 0x1] silence_start: 18.5\n"
    intervals = parse_silencedetect(stderr, duration=20.0)
    assert [(i.start, i.end) for i in intervals] == [(18.5, 20.0)]


def test_negative_start_from_ffmpeg_is_clamped_to_zero():
    # ffmpeg can report a slightly negative silence_start at the very beginning of a file.
    stderr = (
        "[silencedetect @ 0x1] silence_start: -0.001\n"
        "[silencedetect @ 0x1] silence_end: 2.5 | silence_duration: 2.5\n"
    )
    intervals = parse_silencedetect(stderr, duration=20.0)
    assert [(i.start, i.end) for i in intervals] == [(0.0, 2.5)]


def test_no_detection_lines_yields_no_intervals():
    assert parse_silencedetect("frame= 100 fps= 50\n", duration=20.0) == []
