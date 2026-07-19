import dataclasses
import re

from reels.application.ports.caption_renderer import CaptionLine, CaptionWord
from reels.infrastructure.captions.ass_subtitle_builder import CaptionStyle, build_ass

STYLE = CaptionStyle(
    font_family="Amiri",
    base_font_size=64,
    active_font_size=72,
    base_color="&H00FFFFFF",
    active_color="&H0000D7FF",
    position="bottom",
    safe_margin_v=220,
    safe_margin_h=80,
    outline=3,
    shadow=1,
    play_res_x=1080,
    play_res_y=1920,
)

# colour handling isolated from the size "pop"
FLAT = dataclasses.replace(STYLE, active_font_size=STYLE.base_font_size)

ARABIC = [
    CaptionWord("درس", 0.0, 0.4),
    CaptionWord("اليوم", 0.4, 0.9),
    CaptionWord("مهم", 0.9, 1.2),
]
ENGLISH = [
    CaptionWord("The", 0.0, 0.4),
    CaptionWord("Coupling", 0.4, 0.9),
    CaptionWord("Lesson", 0.9, 1.2),
]


def line(words: list[CaptionWord]) -> list[CaptionLine]:
    return [CaptionLine(words=tuple(words))]


def dialogues(ass: str) -> list[str]:
    return [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]


def blocks_of(ass: str, event: int = 0) -> list[tuple[str, str]]:
    """(override_tags, word_text) per word block of one Dialogue event."""
    text = dialogues(ass)[event].split(",,", 1)[1]
    return re.findall(r"\{([^}]*)\}([^{]*)", text)


def flip_start_ms(tags: str) -> int:
    """Start time of the colour-flip transform in an override block."""
    match = re.search(r"\\t\((\d+),\d+,\\1c", tags)
    assert match, f"no colour flip in {tags!r}"
    return int(match.group(1))


def test_ass_has_required_sections_and_resolution():
    ass = build_ass(line([CaptionWord("درس", 0.0, 0.5)]), STYLE)
    assert "[Script Info]" in ass
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "[V4+ Styles]" in ass and "Amiri" in ass
    assert "[Events]" in ass


def test_short_caption_line_is_one_event():
    ass = build_ass(line(ARABIC), FLAT)
    assert len(dialogues(ass)) == 1
    assert len(blocks_of(ass)) == 3
    assert ass.count("\\1c") == 2 * 3  # per word: base anchor + flip target


def test_each_caption_line_gets_its_own_event():
    # phrase boundaries come from the transcript; adjacent lines never merge
    lines = [
        CaptionLine(words=(CaptionWord("درس", 0.0, 0.4),)),
        CaptionLine(words=(CaptionWord("مهم", 0.4, 0.8),)),
    ]
    assert len(dialogues(build_ass(lines, FLAT))) == 2


def test_wide_phrase_splits_into_consecutive_single_row_events():
    # 8 long words cannot fit one visual row at this font size — the line must split
    # in time into several events, preserving spoken order across them.
    words = [
        CaptionWord("استراتيجية" + "ية" * 3, i * 0.5, (i + 1) * 0.5) for i in range(8)
    ]
    ass = build_ass(line(words), FLAT)
    events = dialogues(ass)
    assert len(events) >= 2
    texts = [w.strip() for e in range(len(events)) for _, w in blocks_of(ass, e)]
    assert texts == [w.text for w in words]


def test_split_rows_are_balanced_not_greedy():
    # splitting must not strand a lone word on the last row when a balanced
    # partition exists (e.g. 6 equal words over 2 rows -> 3 + 3)
    words = [CaptionWord("استراتيجيةية", i * 0.5, (i + 1) * 0.5) for i in range(6)]
    ass = build_ass(line(words), FLAT)
    events = dialogues(ass)
    counts = [len(blocks_of(ass, e)) for e in range(len(events))]
    assert min(counts) >= 2


def test_long_pause_inside_a_segment_splits_the_caption():
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("اليوم", 0.4, 0.9),
        CaptionWord("مهم", 2.5, 3.0),  # 1.6s pause
    ]
    ass = build_ass(line(words), FLAT)
    assert len(dialogues(ass)) == 2


def test_event_times_cover_their_own_words_only():
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("مهم", 2.5, 3.0),
    ]
    ass = build_ass(line(words), FLAT)
    first, second = dialogues(ass)
    assert first.split(",")[1] == "0:00:00.00" and first.split(",")[2] == "0:00:00.40"
    assert second.split(",")[1] == "0:00:02.50" and second.split(",")[2] == "0:00:03.00"


def test_karaoke_k_tags_are_not_used():
    # \k fills visually left-to-right in our libass regardless of bidi — it cannot
    # sweep right-to-left, so the builder must not emit it.
    assert "\\k" not in build_ass(line(ARABIC), FLAT)


def test_arabic_line_emits_words_in_spoken_order():
    assert [b[1].strip() for b in blocks_of(build_ass(line(ARABIC), FLAT))] == [
        "درس",
        "اليوم",
        "مهم",
    ]


def test_arabic_line_highlight_sweeps_right_to_left():
    # libass shows the first emitted Arabic word rightmost and maps override blocks to
    # visual slots left-to-right, so the FIRST block must carry the LAST word's window.
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(line(ARABIC), FLAT))]
    assert starts == [900, 400, 0]


def test_english_line_highlight_sweeps_left_to_right():
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(line(ENGLISH), FLAT))]
    assert starts == [0, 400, 900]


def test_embedded_english_run_stays_in_sync():
    # spoken: درس Dependency Injection مهم — visual L->R: مهم Dependency Injection درس,
    # so blocks carry the windows of words [3, 1, 2, 0].
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("Dependency", 0.4, 0.9),
        CaptionWord("Injection", 0.9, 1.5),
        CaptionWord("مهم", 1.5, 2.0),
    ]
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(line(words), FLAT))]
    assert starts == [1500, 400, 900, 0]


def test_split_windows_are_relative_to_their_own_event():
    # after a width split, each event's flips are timed from that EVENT's start
    words = [CaptionWord("استراتيجيةية", i * 1.0, (i + 1) * 1.0) for i in range(6)]
    ass = build_ass(line(words), FLAT)
    events = dialogues(ass)
    for e in range(len(events)):
        starts = [flip_start_ms(tags) for tags, _ in blocks_of(ass, e)]
        assert min(starts) == 0  # some word in each event flips at its event start


def test_direction_override_beats_detection():
    # the mixed line detects rtl (first strong word is Arabic); forcing ltr keeps the
    # run order logical, so the highlight windows come out in spoken order.
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("Dependency", 0.4, 0.9),
        CaptionWord("Injection", 0.9, 1.5),
        CaptionWord("مهم", 1.5, 2.0),
    ]
    ltr = dataclasses.replace(FLAT, direction="ltr")
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(line(words), ltr))]
    assert starts == [0, 400, 900, 1500]


def test_adjacent_words_carry_distinct_colour_lsb():
    # neighbouring words must never share an identical colour at any instant, or libass
    # merges their style runs and the line visibly shifts mid-caption (layout jitter).
    blocks = blocks_of(build_ass(line(ARABIC), FLAT))
    anchors = [re.search(r"\\1c(&H[0-9A-F]{6}&)", tags).group(1) for tags, _ in blocks]
    flips = [re.search(r"\\t\(\d+,\d+,\\1c(&H[0-9A-F]{6}&)\)", tags).group(1) for tags, _ in blocks]
    assert anchors[0] != anchors[1] and anchors[0] == anchors[2]
    assert flips[0] != flips[1] and flips[0] == flips[2]
    # the nudge stays imperceptible: green+red bytes match the config colour exactly
    assert all(a.endswith("FFFF&") for a in anchors)  # base &H00FFFFFF
    assert all(f.endswith("D7FF&") for f in flips)  # active &H0000D7FF


def test_timestamp_format():
    ass = build_ass(line([CaptionWord("x", 61.5, 62.0)]), STYLE)
    assert "0:01:01.50" in ass  # 61.5s -> 0:01:01.50


def test_active_word_grows_to_active_font_size():
    # active (72) > base (64): each word carries an \fs base anchor plus transforms that
    # ramp up to the active size and back — the size "pop".
    ass = build_ass(line(ARABIC[:2]), STYLE)
    assert "\\fs64" in ass
    assert "\\fs72)" in ass
    assert ass.count("\\t(") == 3 * 2  # per word: colour flip + up-ramp + down-ramp


def test_grow_window_follows_the_visual_slot():
    # Arabic pair: first block = leftmost visual slot = LAST spoken word, so its grow
    # up-ramp starts at that word's 400ms offset, not at 0.
    words = [CaptionWord("درس", 0.0, 0.4), CaptionWord("اليوم", 0.4, 0.9)]
    first_tags = blocks_of(build_ass(line(words), STYLE))[0][0]
    assert "\\t(400," in first_tags
    assert ",900,\\fs64)" in first_tags


def test_no_size_transform_when_active_equals_base():
    ass = build_ass(line([CaptionWord("درس", 0.0, 0.5)]), FLAT)
    assert ass.count("\\t(") == 1  # only the colour flip remains
    assert "\\fs" not in ass


def test_empty_lines_still_valid_document():
    ass = build_ass([], STYLE)
    assert "[Events]" in ass
    assert ass.count("Dialogue:") == 0
