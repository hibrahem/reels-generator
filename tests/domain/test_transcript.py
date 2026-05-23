from reels.domain.transcript.transcript import Segment, Transcript, Word


def _transcript() -> Transcript:
    words = [
        Word("درس", 1.0, 1.4),
        Word("اليوم", 1.4, 2.0),
        Word("عن", 5.0, 5.3),
        Word("البرمجة", 5.3, 6.1),
    ]
    seg = Segment(text="درس اليوم عن البرمجة", start=1.0, end=6.1, words=tuple(words))
    return Transcript(source_id="lesson", language="ar", duration_seconds=10.0, segments=(seg,))


def test_words_are_flattened_and_ordered():
    t = _transcript()
    assert [w.text for w in t.words] == ["درس", "اليوم", "عن", "البرمجة"]


def test_snap_start_to_word_boundary():
    t = _transcript()
    # A start at 4.8 should snap forward to the next word start (5.0).
    assert t.snap_start_to_word_boundary(4.8) == 5.0


def test_snap_end_to_word_boundary():
    t = _transcript()
    # An end at 6.3 should snap back to the last word end (6.1).
    assert t.snap_end_to_word_boundary(6.3) == 6.1


def test_words_within_uses_midpoint():
    t = _transcript()
    spoken = t.words_within(4.9, 6.2)
    assert [w.text for w in spoken] == ["عن", "البرمجة"]
