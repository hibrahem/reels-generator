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


def test_ass_has_required_sections_and_resolution():
    ass = build_ass([CaptionWord("درس", 0.0, 0.5)], STYLE)
    assert "[Script Info]" in ass
    assert "PlayResX: 1080" in ass and "PlayResY: 1920" in ass
    assert "[V4+ Styles]" in ass and "Amiri" in ass
    assert "[Events]" in ass


def test_one_karaoke_event_per_chunk():
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("اليوم", 0.4, 0.9),
        CaptionWord("عن", 0.9, 1.2),
    ]
    ass = build_ass(words, STYLE)
    assert ass.count("Dialogue:") == 1  # one line (3 words ≤ max_words_per_line)
    assert ass.count("\\k") == len(words)  # one karaoke tag per word
    assert "درس" in ass and "اليوم" in ass and "عن" in ass  # raw logical text, not pre-shaped


def test_style_uses_configured_karaoke_colours():
    ass = build_ass([CaptionWord("درس", 0.0, 0.5)], STYLE)
    # active = PrimaryColour (sung), base = SecondaryColour (unsung)
    assert "Default,Amiri,64,&H0000D7FF,&H00FFFFFF," in ass


def test_timestamp_format():
    ass = build_ass([CaptionWord("x", 61.5, 62.0)], STYLE)
    assert "0:01:01.50" in ass  # 61.5s -> 0:01:01.50


def test_reverse_word_order_flips_emission():
    import dataclasses

    words = [
        CaptionWord("ريت", 0.0, 0.3),
        CaptionWord("تتخلص", 0.3, 0.7),
        CaptionWord("الموضوع", 0.7, 1.1),
    ]
    normal = build_ass(words, STYLE)
    reversed_ = build_ass(words, dataclasses.replace(STYLE, reverse_word_order=True))
    # normal emits spoken order; reversed emits last-spoken first
    assert normal.index("ريت") < normal.index("الموضوع")
    assert reversed_.index("الموضوع") < reversed_.index("ريت")


def test_active_word_grows_to_active_font_size():
    # active (72) > base (64): each word must carry an \fs base anchor + a \t transform that
    # ramps up to the active size and another that ramps back down — this is the size "pop".
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("اليوم", 0.4, 0.9),
    ]
    ass = build_ass(words, STYLE)
    assert "\\fs64" in ass  # base anchor
    assert "\\fs72" in ass  # active size reached during the word's window
    # one up-ramp + one down-ramp transform per word
    assert ass.count("\\t(") == 2 * len(words)
    # the up-ramp transform animates toward the active size
    assert "\\fs72)" in ass


def test_grow_transform_timing_is_line_relative_milliseconds():
    # second word starts at 0.4s -> 400ms from line start; karaoke window runs to 0.9s -> 900ms.
    words = [
        CaptionWord("درس", 0.0, 0.4),
        CaptionWord("اليوم", 0.4, 0.9),
    ]
    ass = build_ass(words, STYLE)
    # up-ramp for the second word begins at its 400ms line-relative offset
    assert "\\t(400," in ass
    # a down-ramp ends at the word's 900ms window close, returning to base size
    assert ",900,\\fs64)" in ass


def test_no_size_transform_when_active_equals_base():
    import dataclasses

    # base_color == active_color AND active_font_size == base_font_size: nothing to animate,
    # so we emit no \t transforms (only the \k colour sweep, which is a no-op here too).
    style = dataclasses.replace(STYLE, active_font_size=STYLE.base_font_size)
    ass = build_ass([CaptionWord("درس", 0.0, 0.5)], style)
    assert "\\t(" not in ass
    assert "\\k" in ass  # karaoke timing still emitted


def test_karaoke_and_size_override_coexist_per_word():
    # each word block must contain BOTH the \k timing tag and the \fs size machinery.
    words = [CaptionWord("درس", 0.0, 0.4), CaptionWord("اليوم", 0.4, 0.9)]
    ass = build_ass(words, STYLE)
    assert ass.count("\\k") == len(words)
    assert ass.count("\\fs64\\t(") == len(words)  # base anchor immediately followed by transform


def test_empty_words_still_valid_document():
    ass = build_ass([], STYLE)
    assert "[Events]" in ass
    assert ass.count("Dialogue:") == 0
