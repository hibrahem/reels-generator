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


def _use_case(strip: bool) -> CaptionClips:
    return CaptionClips(transcripts=None, renderer=None, manifests=None, strip_punctuation=strip)


def test_strips_punctuation_and_drops_pure_punctuation_tokens():
    words = _use_case(strip=True)._clip_words(_transcript(), 0.0, 60.0)
    texts = [w.text for w in words]
    assert texts == ["يقرأ", "منها", "حلص", "2000"]  # punctuation gone, standalone "؟" dropped


def test_keeps_punctuation_when_disabled():
    words = _use_case(strip=False)._clip_words(_transcript(), 0.0, 60.0)
    assert [w.text for w in words] == ["يقرأ", "منها.", "حلص?", "؟", "2000"]


def test_timing_is_clip_relative():
    words = _use_case(strip=True)._clip_words(_transcript(), 10.0, 11.4)
    assert words[0].start == 0.0  # 10.0 - 10.0
    assert abs(words[0].end - 0.3) < 1e-6
