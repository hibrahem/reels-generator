import pytest

from reels.infrastructure.llm.clip_json import (
    MalformedSelectionResponse,
    parse_clip_candidates,
    strip_code_fences,
)


def test_strip_code_fences():
    assert strip_code_fences('```json\n{"a":1}\n```') == '{"a":1}'
    assert strip_code_fences('```\n{"a":1}\n```') == '{"a":1}'
    assert strip_code_fences('{"a":1}') == '{"a":1}'


def test_parses_valid_clips():
    content = (
        '{"clips":[{"start":10,"end":40,"title":"Coupling intro",'
        '"hook":"إيه هو الـ Coupling؟","caption":"شرح","reason":"standalone",'
        '"confidence":0.9,"visual_dependent":true}]}'
    )
    clips = parse_clip_candidates(content)
    assert len(clips) == 1
    c = clips[0]
    assert c.time_range.start == 10 and c.time_range.end == 40
    assert c.visual_dependent is True
    assert float(c.confidence) == 0.9
    assert "Coupling" in c.hook


def test_parses_fenced_response():
    content = '```json\n{"clips":[{"start":1,"end":30,"confidence":0.5}]}\n```'
    assert len(parse_clip_candidates(content)) == 1


def test_skips_malformed_item_but_keeps_good_ones():
    content = (
        '{"clips":['
        '{"start":50,"end":20,"confidence":0.9},'  # end < start → skipped
        '{"start":10,"end":40,"confidence":0.7}'  # valid
        "]}"
    )
    clips = parse_clip_candidates(content)
    assert len(clips) == 1
    assert clips[0].time_range.start == 10


def test_clamps_out_of_range_confidence():
    content = '{"clips":[{"start":10,"end":40,"confidence":1.5}]}'
    clips = parse_clip_candidates(content)
    assert float(clips[0].confidence) == 1.0


def test_raises_on_invalid_json():
    with pytest.raises(MalformedSelectionResponse):
        parse_clip_candidates("not json at all")


def test_raises_when_clips_key_missing_and_not_a_list():
    with pytest.raises(MalformedSelectionResponse):
        parse_clip_candidates('{"result": "none"}')


def test_empty_clips_is_valid():
    assert parse_clip_candidates('{"clips":[]}') == []
