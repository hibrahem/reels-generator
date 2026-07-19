import dataclasses
import re

from reels.application.ports.caption_renderer import CaptionWord
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
    max_words_per_line=3,
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


def blocks_of(ass: str) -> list[tuple[str, str]]:
    """(override_tags, word_text) per word block of the single Dialogue line."""
    dialogue = next(line for line in ass.splitlines() if line.startswith("Dialogue:"))
    text = dialogue.split(",,", 1)[1]
    return re.findall(r"\{([^}]*)\}([^{]*)", text)


def flip_start_ms(tags: str) -> int:
    """Start time of the colour-flip transform in an override block."""
    match = re.search(r"\\t\((\d+),\d+,\\1c", tags)
    assert match, f"no colour flip in {tags!r}"
    return int(match.group(1))


def test_ass_has_required_sections_and_resolution():
    ass = build_ass([CaptionWord("درس", 0.0, 0.5)], STYLE)
    assert "[Script Info]" in ass
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "[V4+ Styles]" in ass and "Amiri" in ass
    assert "[Events]" in ass


def test_one_event_per_chunk_with_a_colour_flip_per_word():
    ass = build_ass(ARABIC, FLAT)
    assert ass.count("Dialogue:") == 1  # one line (3 words <= max_words_per_line)
    assert len(blocks_of(ass)) == 3
    assert ass.count("\\1c") == 2 * 3  # per word: base anchor + flip target
    assert "درس" in ass and "اليوم" in ass and "عن" not in ass


def test_karaoke_k_tags_are_not_used():
    # \k fills visually left-to-right in our libass regardless of bidi — it cannot
    # sweep right-to-left, so the builder must not emit it.
    ass = build_ass(ARABIC, FLAT)
    assert "\\k" not in ass


def test_arabic_line_emits_words_in_spoken_order():
    assert [b[1].strip() for b in blocks_of(build_ass(ARABIC, FLAT))] == ["درس", "اليوم", "مهم"]


def test_arabic_line_highlight_sweeps_right_to_left():
    # libass shows the first emitted Arabic word rightmost and maps override blocks to
    # visual slots left-to-right, so the FIRST block must carry the LAST word's window.
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(ARABIC, FLAT))]
    assert starts == [900, 400, 0]


def test_english_line_highlight_sweeps_left_to_right():
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(ENGLISH, FLAT))]
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
    style = dataclasses.replace(FLAT, max_words_per_line=4)
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(words, style))]
    assert starts == [1500, 400, 900, 0]


def test_direction_override_beats_detection():
    # the mixed line detects rtl (first strong word is Arabic); forcing ltr keeps the
    # run order logical, so the highlight windows come out in spoken order.
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("Dependency", 0.4, 0.9),
        CaptionWord("Injection", 0.9, 1.5),
        CaptionWord("مهم", 1.5, 2.0),
    ]
    ltr = dataclasses.replace(FLAT, max_words_per_line=4, direction="ltr")
    starts = [flip_start_ms(tags) for tags, _ in blocks_of(build_ass(words, ltr))]
    assert starts == [0, 400, 900, 1500]


def test_adjacent_words_carry_distinct_colour_lsb():
    # neighbouring words must never share an identical colour at any instant, or libass
    # merges their style runs and the line visibly shifts mid-caption (layout jitter).
    blocks = blocks_of(build_ass(ARABIC, FLAT))
    anchors = [re.search(r"\\1c(&H[0-9A-F]{6}&)", tags).group(1) for tags, _ in blocks]
    flips = [re.search(r"\\t\(\d+,\d+,\\1c(&H[0-9A-F]{6}&)\)", tags).group(1) for tags, _ in blocks]
    assert anchors[0] != anchors[1] and anchors[0] == anchors[2]
    assert flips[0] != flips[1] and flips[0] == flips[2]
    # the nudge stays imperceptible: green+red bytes match the config colour exactly
    assert all(a.endswith("FFFF&") for a in anchors)  # base &H00FFFFFF
    assert all(f.endswith("D7FF&") for f in flips)  # active &H0000D7FF


def test_timestamp_format():
    ass = build_ass([CaptionWord("x", 61.5, 62.0)], STYLE)
    assert "0:01:01.50" in ass  # 61.5s -> 0:01:01.50


def test_active_word_grows_to_active_font_size():
    # active (72) > base (64): each word carries an \fs base anchor plus transforms that
    # ramp up to the active size and back — the size "pop".
    ass = build_ass(ARABIC[:2], STYLE)
    assert "\\fs64" in ass
    assert "\\fs72)" in ass
    assert ass.count("\\t(") == 3 * 2  # per word: colour flip + up-ramp + down-ramp


def test_grow_window_follows_the_visual_slot():
    # Arabic pair: first block = leftmost visual slot = LAST spoken word, so its grow
    # up-ramp starts at that word's 400ms offset, not at 0.
    words = [CaptionWord("درس", 0.0, 0.4), CaptionWord("اليوم", 0.4, 0.9)]
    first_tags = blocks_of(build_ass(words, STYLE))[0][0]
    assert "\\t(400," in first_tags
    assert ",900,\\fs64)" in first_tags


def test_no_size_transform_when_active_equals_base():
    ass = build_ass([CaptionWord("درس", 0.0, 0.5)], FLAT)
    assert ass.count("\\t(") == 1  # only the colour flip remains
    assert "\\fs" not in ass


def test_empty_words_still_valid_document():
    ass = build_ass([], STYLE)
    assert "[Events]" in ass
    assert ass.count("Dialogue:") == 0
