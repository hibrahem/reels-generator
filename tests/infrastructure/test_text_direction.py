"""Word-level bidi planning for caption lines (see ass_subtitle_builder docstring).

Our vendored libass lays lines out with an immovable LTR base paragraph direction and maps
per-word override blocks onto VISUAL word slots left-to-right. To control both the visual
word order and which spoken window highlights each slot, the builder needs:

  - visual_order:  V[j] = logical word index shown at visual slot j (left-to-right)
  - emission_order: E[j] = logical word index to EMIT at text position j, chosen so that
    libass's own LTR-base bidi (which reverses each run of RTL words) produces exactly V.
"""

from reels.infrastructure.captions.text_direction import (
    line_direction,
    plan_line,
    word_direction,
)


class TestWordDirection:
    def test_arabic_word_is_rtl(self):
        assert word_direction("درس") == "rtl"

    def test_latin_word_is_ltr(self):
        assert word_direction("Coupling") == "ltr"

    def test_number_has_no_strong_direction(self):
        assert word_direction("123") is None

    def test_leading_punctuation_is_skipped(self):
        assert word_direction("«مهم»") == "rtl"


class TestLineDirection:
    def test_arabic_first_word_makes_line_rtl(self):
        assert line_direction(["درس", "Coupling"]) == "rtl"

    def test_english_first_word_makes_line_ltr(self):
        assert line_direction(["The", "درس"]) == "ltr"

    def test_neutral_first_word_defers_to_next_strong_word(self):
        assert line_direction(["123", "درس"]) == "rtl"

    def test_line_with_no_strong_words_defaults_rtl(self):
        assert line_direction(["123", "456"]) == "rtl"


class TestPlanLineRtl:
    def test_pure_arabic_line_mirrors_visual_order_and_emits_logical(self):
        # spoken A B C -> displayed C B A (A rightmost); emit logically, libass reverses.
        visual, emission = plan_line(["درس", "اليوم", "مهم"], "rtl")
        assert visual == [2, 1, 0]
        assert emission == [0, 1, 2]

    def test_embedded_english_run_keeps_internal_ltr_order(self):
        # spoken: درس Dependency Injection مهم -> visual L->R: مهم Dependency Injection درس
        visual, emission = plan_line(["درس", "Dependency", "Injection", "مهم"], "rtl")
        assert visual == [3, 1, 2, 0]
        assert emission == [3, 1, 2, 0]

    def test_arabic_pair_inside_line_reverses_within_its_run(self):
        # spoken: درس اليوم Coupling مهم -> runs R[0,1] L[2] R[3]
        # visual L->R: مهم Coupling اليوم درس; emission re-reverses R segments for libass.
        visual, emission = plan_line(["درس", "اليوم", "Coupling", "مهم"], "rtl")
        assert visual == [3, 2, 1, 0]
        assert emission == [3, 2, 0, 1]

    def test_neutral_word_joins_surrounding_arabic_run(self):
        visual, emission = plan_line(["درس", "123", "مهم"], "rtl")
        assert visual == [2, 1, 0]
        assert emission == [0, 1, 2]


class TestPlanLineLtr:
    def test_pure_english_line_is_identity(self):
        visual, emission = plan_line(["The", "Coupling", "Lesson"], "ltr")
        assert visual == [0, 1, 2]
        assert emission == [0, 1, 2]

    def test_arabic_run_still_reads_right_to_left_in_ltr_paragraph(self):
        # paragraph direction orders runs; a run of Arabic words always reads RTL,
        # so a single-run Arabic line renders identically under ltr and rtl.
        visual, emission = plan_line(["درس", "اليوم", "مهم"], "ltr")
        assert visual == [2, 1, 0]
        assert emission == [0, 1, 2]

    def test_embedded_arabic_word_keeps_slot_in_ltr_line(self):
        visual, emission = plan_line(["The", "درس", "Lesson"], "ltr")
        assert visual == [0, 1, 2]
        assert emission == [0, 1, 2]

    def test_embedded_arabic_pair_reverses_within_its_run_in_ltr_line(self):
        visual, emission = plan_line(["The", "درس", "اليوم", "Lesson"], "ltr")
        assert visual == [0, 2, 1, 3]
        assert emission == [0, 1, 2, 3]

    def test_ltr_and_rtl_differ_only_in_run_order_on_mixed_lines(self):
        words = ["درس", "Dependency", "Injection", "مهم"]
        assert plan_line(words, "ltr")[0] == [0, 1, 2, 3]
        assert plan_line(words, "rtl")[0] == [3, 1, 2, 0]
