from reels.domain.reel.layout_plan import PresenterDetection, ReframeMode
from reels.domain.services.presenter_crop_planner import PresenterCropPlanner
from reels.domain.shared.value_objects import CropRectangle, Resolution

HD = Resolution(1920, 1080)


def _reliable(box: CropRectangle) -> PresenterDetection:
    return PresenterDetection(box=box, stability=0.9, sampled_frames=10)


def test_full_height_nine_sixteen_column_for_16x9_source():
    planner = PresenterCropPlanner()
    # presenter face centered around x=1500 (right side)
    plan = planner.plan_mode_a(HD, _reliable(CropRectangle(x=1440, y=200, width=120, height=160)))
    crop = plan.presenter_crop
    assert plan.mode is ReframeMode.PRESENTER_ONLY
    assert crop.height == 1080  # full height
    assert abs(crop.width / crop.height - 9 / 16) < 0.01  # ~9:16
    assert crop.fits_within(HD)
    # centered on the face center (x=1500): x ≈ 1500 - width/2
    assert abs((crop.x + crop.width // 2) - 1500) <= 1
    assert plan.fallback_used is False


def test_clamps_when_presenter_near_right_edge():
    planner = PresenterCropPlanner()
    plan = planner.plan_mode_a(HD, _reliable(CropRectangle(x=1860, y=100, width=80, height=120)))
    assert plan.presenter_crop.fits_within(HD)
    assert plan.presenter_crop.x + plan.presenter_crop.width == HD.width  # flush to right edge


def test_unreliable_detection_falls_back_to_right_anchor_and_flags():
    planner = PresenterCropPlanner()
    plan = planner.plan_mode_a(HD, PresenterDetection(box=None, stability=0.0, sampled_frames=8))
    assert plan.fallback_used is True
    assert plan.warnings  # flagged for human review
    # right-anchored column flush to the right edge
    assert plan.presenter_crop.x + plan.presenter_crop.width == HD.width


def test_left_anchor_fallback():
    planner = PresenterCropPlanner()
    plan = planner.plan_mode_a(
        HD, PresenterDetection(box=None, stability=0.2, sampled_frames=8), anchor="left"
    )
    assert plan.presenter_crop.x == 0
