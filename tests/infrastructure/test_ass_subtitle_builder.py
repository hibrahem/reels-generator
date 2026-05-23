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


def test_empty_words_still_valid_document():
    ass = build_ass([], STYLE)
    assert "[Events]" in ass
    assert ass.count("Dialogue:") == 0
