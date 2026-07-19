"""Re-rendered reels must actually reach the browser.

The media endpoints serve files that get replaced in place when a reel is re-processed.
Without explicit cache directives, browsers apply heuristic freshness to the response and
keep showing the OLD video for days after a re-render — which looks like "processing a
reel produced no new video". These tests pin the contract: media responses demand
revalidation, and the API exposes a render version the UI can use to bust its URL.
"""

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")

from reels.application.manifest import Manifest  # noqa: E402
from reels.domain.reel.clip_selection import ClipCandidate  # noqa: E402
from reels.domain.reel.reel import Reel  # noqa: E402
from reels.domain.shared.value_objects import Confidence, TimeRange  # noqa: E402
from reels.domain.source_video.source_video import SourceVideo, SourceVideoId  # noqa: E402
from reels.infrastructure.persistence.json_manifest_repository import (  # noqa: E402
    JsonManifestRepository,
)


@pytest.fixture()
def studio(tmp_path):
    """A test client plus a manifest for one packaged reel whose output file exists."""
    from fastapi.testclient import TestClient

    from reels.presentation.api.app import create_app

    for name in ("input", "output", "work"):
        (tmp_path / name).mkdir()
    font = tmp_path / "font.ttf"
    font.write_bytes(b"")
    config = tmp_path / "config.yaml"
    config.write_text(
        f"paths:\n"
        f"  input_dir: {tmp_path / 'input'}\n"
        f"  output_dir: {tmp_path / 'output'}\n"
        f"  work_dir: {tmp_path / 'work'}\n"
        f"  font: {font}\n",
        encoding="utf-8",
    )

    source_path = tmp_path / "input" / "lecture.mp4"
    source_path.write_bytes(b"source-bytes")
    working_dir = tmp_path / "work" / "lecture"
    reel = Reel(
        source_id="lecture",
        index=1,
        candidate=ClipCandidate(
            time_range=TimeRange(start=0.0, end=10.0),
            title="Intro to Coupling",
            hook="",
            caption="",
            reason="",
            confidence=Confidence(0.9),
        ),
    )
    final = working_dir / "final" / "reel_01.mp4"
    final.parent.mkdir(parents=True)
    final.write_bytes(b"rendered-video")
    reel.finalize(final)
    output = tmp_path / "output" / reel.output_filename()
    output.write_bytes(b"rendered-video")

    manifest = Manifest(
        source=SourceVideo(
            id=SourceVideoId("lecture"), path=source_path, working_dir=working_dir
        ),
        reels=[reel],
    )
    JsonManifestRepository(tmp_path / "work").save(manifest)
    return TestClient(create_app(config)), output


def test_reel_media_demands_revalidation_so_rerenders_replace_cached_video(studio):
    client, _ = studio
    res = client.get("/api/videos/lecture/reels/1/media")
    assert res.status_code == 200, res.text
    assert res.headers.get("cache-control") == "no-cache"


def test_source_media_demands_revalidation(studio):
    client, _ = studio
    res = client.get("/api/videos/lecture/media")
    assert res.status_code == 200, res.text
    assert res.headers.get("cache-control") == "no-cache"


def test_reel_reports_render_version_for_cache_busting(studio):
    client, output = studio
    reel = client.get("/api/videos/lecture").json()["reels"][0]
    assert reel["rendered_at"] == pytest.approx(output.stat().st_mtime)


def test_unrendered_reel_has_no_render_version(studio, tmp_path):
    client, output = studio
    output.unlink()
    (tmp_path / "work" / "lecture" / "final" / "reel_01.mp4").unlink()
    reel = client.get("/api/videos/lecture").json()["reels"][0]
    assert reel["rendered_at"] is None
