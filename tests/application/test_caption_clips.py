from reels.application.use_cases.caption_clips import CaptionClips
from reels.domain.transcript.transcript import Segment, Transcript, Word


def _transcript() -> Transcript:
    words = (
        Word("يقرأ", 10.0, 10.3),
        Word("منها.", 10.3, 10.6),  # trailing period
        Word("حلص?", 10.6, 10.9),  # trailing ASCII question mark
        Word("؟", 10.9, 11.0),  # standalone punctuation token
        Word("2000", 11.0, 11.4),  # digits must survive
    )
    seg = Segment(text="...", start=10.0, end=11.4, words=words)
    return Transcript(source_id="s", language="ar", duration_seconds=60.0, segments=(seg,))


def _two_segment_transcript() -> Transcript:
    first = Segment(
        text="...",
        start=10.0,
        end=10.6,
        words=(Word("يقرأ", 10.0, 10.3), Word("منها", 10.3, 10.6)),
    )
    second = Segment(
        text="...",
        start=10.7,
        end=11.0,
        words=(Word("درس", 10.7, 11.0),),
    )
    return Transcript(
        source_id="s", language="ar", duration_seconds=60.0, segments=(first, second)
    )


def _use_case(strip: bool = True) -> CaptionClips:
    return CaptionClips(transcripts=None, renderer=None, manifests=None, strip_punctuation=strip)


def _flat_texts(lines) -> list[str]:
    return [w.text for line in lines for w in line.words]


def test_strips_punctuation_and_drops_pure_punctuation_tokens():
    lines = _use_case(strip=True)._clip_lines(_transcript(), 0.0, 60.0)
    assert _flat_texts(lines) == ["يقرأ", "منها", "حلص", "2000"]


def test_keeps_punctuation_when_disabled():
    lines = _use_case(strip=False)._clip_lines(_transcript(), 0.0, 60.0)
    assert _flat_texts(lines) == ["يقرأ", "منها.", "حلص?", "؟", "2000"]


def test_timing_is_clip_relative():
    lines = _use_case()._clip_lines(_transcript(), 10.0, 11.4)
    first = lines[0].words[0]
    assert first.start == 0.0  # 10.0 - 10.0
    assert abs(first.end - 0.3) < 1e-6


def test_each_transcript_segment_becomes_its_own_caption_line():
    # caption phrasing mirrors the transcript view: one line per segment
    lines = _use_case()._clip_lines(_two_segment_transcript(), 0.0, 60.0)
    assert [[w.text for w in line.words] for line in lines] == [["يقرأ", "منها"], ["درس"]]


def test_segment_outside_the_clip_window_is_dropped():
    lines = _use_case()._clip_lines(_two_segment_transcript(), 10.65, 60.0)
    assert [[w.text for w in line.words] for line in lines] == [["درس"]]


def test_segment_reduced_to_nothing_by_stripping_is_dropped():
    seg = Segment(text="؟", start=10.0, end=10.2, words=(Word("؟", 10.0, 10.2),))
    transcript = Transcript(
        source_id="s", language="ar", duration_seconds=60.0, segments=(seg,)
    )
    assert _use_case()._clip_lines(transcript, 0.0, 60.0) == []
