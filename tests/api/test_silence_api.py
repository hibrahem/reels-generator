"""End-to-end: upload a video with a silent middle, get back a shorter one."""

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi", reason="web extra not installed")

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


@pytest.fixture()
def client(tmp_path):
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
    return TestClient(create_app(config))


@pytest.fixture()
def noisy_video(tmp_path) -> Path:
    """6s clip: 2s tone, 2s silence, 2s tone."""
    path = tmp_path / "fixture.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
            "-f", "lavfi", "-i", "color=c=black:s=160x120:d=6:r=15",
            "-filter_complex", "[0:a]volume='if(between(t,2,4),0,1)':eval=frame[a]",
            "-map", "1:v", "-map", "[a]",
            "-c:v", "libx264", "-c:a", "aac", "-shortest",
            str(path),
        ],
        check=True, capture_output=True,
    )
    return path


def _wait_for_job(client, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.25)
    pytest.fail(f"job {job_id} did not finish within {timeout}s")


def test_silent_middle_is_removed_end_to_end(client, noisy_video):
    with noisy_video.open("rb") as f:
        res = client.post(
            "/api/silence/jobs",
            files={"file": ("fixture.mp4", f, "video/mp4")},
            data={"threshold_db": -35.0, "min_silence": 0.6, "padding": 0.15},
        )
    assert res.status_code == 200, res.text
    body = res.json()

    job = _wait_for_job(client, body["job_id"])
    assert job["state"] == "done", json.dumps(job, indent=2)

    result = client.get(f"/api/silence/jobs/{body['token']}/result")
    assert result.status_code == 200
    stats = result.json()
    assert stats["cuts_removed"] == 1
    assert stats["output_duration"] < stats["original_duration"]
    assert stats["output_filename"] == "fixture.nosilence.mp4"

    download = client.get(f"/api/silence/jobs/{body['token']}/download")
    assert download.status_code == 200
    assert len(download.content) > 0


def test_result_is_not_found_for_unknown_token(client):
    assert client.get("/api/silence/jobs/deadbeef1234/result").status_code == 404
