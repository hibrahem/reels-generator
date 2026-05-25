from pathlib import Path

from reels.application.pipeline_stage import Stage
from reels.application.run_options import resume_stage_for_reel
from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.layout_plan import CropRectangle, LayoutPlan, ReframeMode
from reels.domain.reel.reel import Reel
from reels.domain.shared.value_objects import Confidence, TimeRange


def _reel() -> Reel:
    c = ClipCandidate(TimeRange(10, 40), "A Title", "hook", "cap", "r", Confidence(0.9))
    return Reel(source_id="s", index=1, candidate=c)


def _layout() -> LayoutPlan:
    return LayoutPlan(mode=ReframeMode.PRESENTER_ONLY, presenter_crop=CropRectangle(0, 0, 100, 200))


def test_fresh_reel_resumes_at_plan_layout(tmp_path):
    assert resume_stage_for_reel(_reel(), tmp_path) is Stage.PLAN_LAYOUT


def test_resumes_at_first_incomplete_stage(tmp_path):
    # plan-layout + cut done, reframe not → resume at reframe
    r = _reel()
    r.plan_layout(_layout())
    r.record_cut(Path("cut.mp4"))
    assert resume_stage_for_reel(r, tmp_path) is Stage.REFRAME


def test_stopped_after_caption_resumes_at_brand(tmp_path):
    # The bug scenario: everything through caption is done → resume at brand, not the beginning.
    r = _reel()
    r.plan_layout(_layout())
    r.record_cut(Path("cut.mp4"))
    r.record_reframe(Path("reframe.mp4"))
    r.record_captioned(Path("caption.mp4"))
    assert resume_stage_for_reel(r, tmp_path) is Stage.BRAND


def test_branded_but_not_packaged_resumes_at_package(tmp_path):
    r = _reel()
    r.plan_layout(_layout())
    r.record_cut(Path("cut.mp4"))
    r.record_reframe(Path("reframe.mp4"))
    r.record_captioned(Path("caption.mp4"))
    r.finalize(Path("final.mp4"))
    # output file does not exist in tmp_path → package still pending
    assert resume_stage_for_reel(r, tmp_path) is Stage.PACKAGE


def test_fully_packaged_reel_does_a_full_rerender(tmp_path):
    r = _reel()
    r.plan_layout(_layout())
    r.record_cut(Path("cut.mp4"))
    r.record_reframe(Path("reframe.mp4"))
    r.record_captioned(Path("caption.mp4"))
    r.finalize(Path("final.mp4"))
    (tmp_path / r.output_filename()).write_text("")  # output exists → packaged
    # all stages complete → "Process" re-renders from the start
    assert resume_stage_for_reel(r, tmp_path) is Stage.PLAN_LAYOUT
