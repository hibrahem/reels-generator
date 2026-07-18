# Silence Remover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A standalone "Silence Remover" tool in Reels Studio: upload a video, one click, download a copy with all silent passages removed.

**Architecture:** DDD layers matching the existing codebase — pure segment math in `domain/silence_removal/`, a `RemoveSilence` use case behind two new ports (`SilenceDetector`, `SegmentCutter`), ffmpeg adapters in `infrastructure/ffmpeg/`, a FastAPI router using the existing background `JobManager` + SSE, and a new React tab. Fully independent of the reels pipeline (no manifest, no stages).

**Tech Stack:** Python 3.12, ffmpeg `silencedetect` + trim/concat `filter_complex`, FastAPI, React + TanStack Query + Tailwind (existing stack). No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-07-18-silence-removal-design.md`

## Global Constraints

- Python `>=3.12,<3.13`; run everything through `uv` (`uv run pytest`, `uv run ruff check src tests`).
- No new runtime dependencies. One new **dev** dependency: `httpx` (required by `fastapi.testclient`), added in Task 5.
- Defaults (exact values, used in backend and UI): silence threshold **−35.0 dB**, min silence duration **0.6 s**, edge padding **0.15 s**.
- Domain layer imports nothing from application/infrastructure/presentation. Ports are ABCs in `src/reels/application/ports/`. Concrete adapters in `src/reels/infrastructure/ffmpeg/`. Wiring only in `src/reels/presentation/container.py`.
- Reuse the shared-kernel `TimeRange` value object (`reels.domain.shared.value_objects`) for both silence intervals and keep segments — do not invent duplicate interval types.
- Time epsilon convention in this codebase is `1e-3` (see `value_objects.py`); `TimeRange` rejects ranges shorter than that.
- Frontend: the API base is `/api`; multipart uploads must NOT set a `Content-Type` header manually (the browser sets the boundary).
- Commit after each task with a conventional-commit message ending in the `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.
- Beads issue for this work: `rg-7ol` (leave open until the final task).

---

### Task 1: Domain — keep-segment math

**Files:**
- Create: `src/reels/domain/silence_removal/__init__.py` (empty)
- Create: `src/reels/domain/silence_removal/keep_segments.py`
- Test: `tests/domain/test_keep_segments.py`

**Interfaces:**
- Consumes: `TimeRange`, `DomainError` from the shared kernel.
- Produces (used by Task 2):
  - `compute_keep_segments(silences: Sequence[TimeRange], video_duration: float, *, min_silence: float, padding: float) -> SilenceCutPlan`
  - `SilenceCutPlan` frozen dataclass: `keep_segments: tuple[TimeRange, ...]`, `cuts_removed: int`, property `output_duration: float`
  - `FullySilentVideo(DomainError)`

Semantics: a detected silence shorter than `min_silence` is left alone. Each cut is shrunk by `padding` seconds on both sides (so speech isn't clipped) — **except** at the file edges (silence starting at ~0 cuts from 0; silence ending at ~`video_duration` cuts to the end), where there is no adjacent speech to protect. Overlapping/adjacent cut regions merge; `cuts_removed` counts merged regions. Keep-slivers shorter than 0.05 s are absorbed into the neighboring cut. An empty keep list raises `FullySilentVideo`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/domain/test_keep_segments.py
"""Silence-removal segment math (pure domain, no mocks)."""

import pytest

from reels.domain.shared.value_objects import TimeRange
from reels.domain.silence_removal.keep_segments import (
    FullySilentVideo,
    compute_keep_segments,
)


def _spans(plan):
    return [(round(s.start, 3), round(s.end, 3)) for s in plan.keep_segments]


def test_video_without_silence_is_kept_whole():
    plan = compute_keep_segments([], 10.0, min_silence=0.6, padding=0.15)
    assert _spans(plan) == [(0.0, 10.0)]
    assert plan.cuts_removed == 0
    assert plan.output_duration == pytest.approx(10.0)


def test_mid_video_silence_is_cut_with_padding_kept_on_both_sides():
    plan = compute_keep_segments(
        [TimeRange(4.0, 6.0)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(0.0, 4.15), (5.85, 10.0)]
    assert plan.cuts_removed == 1
    assert plan.output_duration == pytest.approx(8.3)


def test_silence_shorter_than_minimum_is_left_alone():
    plan = compute_keep_segments(
        [TimeRange(4.0, 4.4)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(0.0, 10.0)]
    assert plan.cuts_removed == 0


def test_silence_at_file_start_is_cut_without_leading_padding():
    plan = compute_keep_segments(
        [TimeRange(0.0, 2.0)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(1.85, 10.0)]
    assert plan.cuts_removed == 1


def test_silence_at_file_end_is_cut_without_trailing_padding():
    plan = compute_keep_segments(
        [TimeRange(8.0, 10.0)], 10.0, min_silence=0.6, padding=0.15
    )
    assert _spans(plan) == [(0.0, 8.15)]
    assert plan.cuts_removed == 1


def test_fully_silent_video_is_rejected():
    with pytest.raises(FullySilentVideo):
        compute_keep_segments([TimeRange(0.0, 10.0)], 10.0, min_silence=0.6, padding=0.15)


def test_overlapping_silences_merge_into_one_cut():
    plan = compute_keep_segments(
        [TimeRange(2.0, 4.0), TimeRange(3.5, 6.0)], 10.0, min_silence=0.6, padding=0.0
    )
    assert _spans(plan) == [(0.0, 2.0), (6.0, 10.0)]
    assert plan.cuts_removed == 1


def test_unsorted_silences_are_handled():
    plan = compute_keep_segments(
        [TimeRange(6.0, 7.0), TimeRange(2.0, 3.0)], 10.0, min_silence=0.6, padding=0.0
    )
    assert _spans(plan) == [(0.0, 2.0), (3.0, 6.0), (7.0, 10.0)]
    assert plan.cuts_removed == 2


def test_padding_wider_than_silence_cancels_the_cut():
    # 0.7s silence, 0.4s padding per side -> nothing left to cut.
    plan = compute_keep_segments(
        [TimeRange(4.0, 4.7)], 10.0, min_silence=0.6, padding=0.4
    )
    assert _spans(plan) == [(0.0, 10.0)]
    assert plan.cuts_removed == 0


def test_tiny_keep_sliver_between_cuts_is_absorbed():
    # 0.03s of audio between two cuts is below the 0.05s sliver floor.
    plan = compute_keep_segments(
        [TimeRange(2.0, 4.0), TimeRange(4.03, 6.0)], 10.0, min_silence=0.6, padding=0.0
    )
    assert _spans(plan) == [(0.0, 2.0), (6.0, 10.0)]
    assert plan.cuts_removed == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/domain/test_keep_segments.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'reels.domain.silence_removal'`

- [ ] **Step 3: Implement the domain module**

Create empty `src/reels/domain/silence_removal/__init__.py`, then:

```python
# src/reels/domain/silence_removal/keep_segments.py
"""Pure segment math for silence removal: detected silences in, keep-segments out."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from reels.domain.shared.exceptions import DomainError
from reels.domain.shared.value_objects import TimeRange

_EPSILON = 1e-3
# Keep-slivers shorter than this are absorbed into the neighboring cut (sub-frame noise).
_MIN_KEEP = 0.05


class FullySilentVideo(DomainError):
    """Removing silence would leave nothing — the whole video is silent."""


@dataclass(frozen=True, slots=True)
class SilenceCutPlan:
    """The segments of the source to keep, in order, and how many cut regions were removed."""

    keep_segments: tuple[TimeRange, ...]
    cuts_removed: int

    @property
    def output_duration(self) -> float:
        return sum(s.duration for s in self.keep_segments)


def compute_keep_segments(
    silences: Sequence[TimeRange],
    video_duration: float,
    *,
    min_silence: float,
    padding: float,
) -> SilenceCutPlan:
    """Turn detected silences into the plan of segments to keep.

    Silences shorter than ``min_silence`` are left alone. Each cut keeps ``padding`` seconds
    of audio on both sides so speech is not clipped — except at the file edges, where there
    is no adjacent speech to protect.
    """
    cuts: list[tuple[float, float]] = []
    for s in sorted(silences, key=lambda s: s.start):
        if s.duration < min_silence:
            continue
        start = 0.0 if s.start <= _EPSILON else s.start + padding
        end = video_duration if s.end >= video_duration - _EPSILON else s.end - padding
        if end - start > _EPSILON:
            cuts.append((max(start, 0.0), min(end, video_duration)))

    merged: list[list[float]] = []
    for start, end in cuts:
        if merged and start <= merged[-1][1] + _MIN_KEEP:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    keep: list[TimeRange] = []
    cursor = 0.0
    for start, end in merged:
        if start - cursor > _MIN_KEEP:
            keep.append(TimeRange(cursor, start))
        cursor = max(cursor, end)
    if video_duration - cursor > _MIN_KEEP:
        keep.append(TimeRange(cursor, video_duration))

    if not keep:
        raise FullySilentVideo(
            f"nothing left to keep: the whole {video_duration:.1f}s video is silent"
        )
    return SilenceCutPlan(keep_segments=tuple(keep), cuts_removed=len(merged))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/domain/test_keep_segments.py -v`
Expected: all 10 PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/reels/domain/silence_removal tests/domain/test_keep_segments.py
git add src/reels/domain/silence_removal tests/domain/test_keep_segments.py
git commit -m "feat: domain segment math for silence removal

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Application — ports and RemoveSilence use case

**Files:**
- Create: `src/reels/application/ports/silence_detector.py`
- Create: `src/reels/application/ports/segment_cutter.py`
- Create: `src/reels/application/use_cases/remove_silence.py`
- Test: `tests/application/test_remove_silence.py`

**Interfaces:**
- Consumes: `compute_keep_segments`/`FullySilentVideo` (Task 1); existing `VideoProber` port (`reels.domain.source_video.video_prober`) whose `probe(path)` returns `VideoMetadata(duration_seconds, resolution, fps, has_audio, video_codec, audio_codec)`.
- Produces (used by Tasks 3–5):
  - `SilenceDetector.detect(video_path: Path, *, threshold_db: float, min_silence: float, duration: float) -> list[TimeRange]`
  - `SegmentCutter.cut(video_path: Path, segments: Sequence[TimeRange], out_path: Path) -> None`
  - `SilenceRemovalSettings(threshold_db=-35.0, min_silence=0.6, padding=0.15)` (frozen dataclass)
  - `SilenceRemovalResult(original_duration: float, output_duration: float, cuts_removed: int)` (frozen dataclass)
  - `NoAudioTrack(Exception)`
  - `RemoveSilence(prober=, detector=, cutter=).execute(video_path, out_path, settings=SilenceRemovalSettings(), on_progress=None) -> SilenceRemovalResult` where `on_progress: Callable[[str, str], None] | None` receives `(stage, message)` with stages `"probe" | "detect" | "cut"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/application/test_remove_silence.py
"""RemoveSilence use case orchestration, with fake ports (no ffmpeg)."""

from pathlib import Path

import pytest

from reels.application.ports.segment_cutter import SegmentCutter
from reels.application.ports.silence_detector import SilenceDetector
from reels.application.use_cases.remove_silence import (
    NoAudioTrack,
    RemoveSilence,
    SilenceRemovalSettings,
)
from reels.domain.shared.value_objects import Resolution, TimeRange
from reels.domain.source_video.video_metadata import VideoMetadata
from reels.domain.source_video.video_prober import VideoProber


class FakeProber(VideoProber):
    def __init__(self, duration: float = 10.0, has_audio: bool = True) -> None:
        self._duration = duration
        self._has_audio = has_audio

    def probe(self, path: Path) -> VideoMetadata:
        return VideoMetadata(
            duration_seconds=self._duration,
            resolution=Resolution(640, 480),
            fps=30.0,
            has_audio=self._has_audio,
            video_codec="h264",
            audio_codec="aac" if self._has_audio else None,
        )


class FakeDetector(SilenceDetector):
    def __init__(self, silences: list[TimeRange]) -> None:
        self._silences = silences

    def detect(self, video_path, *, threshold_db, min_silence, duration):
        return self._silences


class FakeCutter(SegmentCutter):
    def __init__(self) -> None:
        self.calls: list[tuple[Path, tuple, Path]] = []

    def cut(self, video_path, segments, out_path):
        self.calls.append((video_path, tuple(segments), out_path))
        out_path.write_bytes(b"trimmed")


def _use_case(prober=None, detector=None, cutter=None):
    return RemoveSilence(
        prober=prober or FakeProber(),
        detector=detector or FakeDetector([]),
        cutter=cutter or FakeCutter(),
    )


def test_video_without_audio_cannot_have_silence_removed(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    with pytest.raises(NoAudioTrack):
        _use_case(prober=FakeProber(has_audio=False)).execute(src, tmp_path / "out.mp4")


def test_silences_are_cut_and_result_reports_durations(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    out = tmp_path / "out.mp4"
    cutter = FakeCutter()
    result = _use_case(
        detector=FakeDetector([TimeRange(4.0, 6.0)]), cutter=cutter
    ).execute(src, out, SilenceRemovalSettings(padding=0.15))

    assert len(cutter.calls) == 1
    _, segments, _ = cutter.calls[0]
    assert [(round(s.start, 3), round(s.end, 3)) for s in segments] == [
        (0.0, 4.15),
        (5.85, 10.0),
    ]
    assert result.original_duration == pytest.approx(10.0)
    assert result.output_duration == pytest.approx(8.3)
    assert result.cuts_removed == 1


def test_video_with_no_silence_is_copied_unchanged(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"original-bytes")
    out = tmp_path / "out.mp4"
    cutter = FakeCutter()
    result = _use_case(detector=FakeDetector([]), cutter=cutter).execute(src, out)

    assert cutter.calls == []
    assert out.read_bytes() == b"original-bytes"
    assert result.cuts_removed == 0
    assert result.output_duration == pytest.approx(result.original_duration)


def test_progress_stages_are_emitted_in_order(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    stages: list[str] = []
    _use_case(detector=FakeDetector([TimeRange(4.0, 6.0)])).execute(
        src, tmp_path / "out.mp4", on_progress=lambda stage, msg: stages.append(stage)
    )
    assert stages == ["probe", "detect", "cut"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/application/test_remove_silence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'reels.application.ports.segment_cutter'`

- [ ] **Step 3: Implement ports and use case**

```python
# src/reels/application/ports/silence_detector.py
"""Port for detecting silent passages in a video's audio track."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from reels.domain.shared.value_objects import TimeRange


class SilenceDetector(ABC):
    @abstractmethod
    def detect(
        self, video_path: Path, *, threshold_db: float, min_silence: float, duration: float
    ) -> list[TimeRange]:
        """Return intervals where audio stays below ``threshold_db`` for >= ``min_silence`` s.

        ``duration`` is the video's total length, used to close a silence that runs to the end.
        """
        raise NotImplementedError
```

```python
# src/reels/application/ports/segment_cutter.py
"""Port for rendering a copy of a video that keeps only the given segments."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path

from reels.domain.shared.value_objects import TimeRange


class SegmentCutter(ABC):
    @abstractmethod
    def cut(self, video_path: Path, segments: Sequence[TimeRange], out_path: Path) -> None:
        """Write ``out_path`` containing only ``segments`` of ``video_path``, concatenated in order."""
        raise NotImplementedError
```

```python
# src/reels/application/use_cases/remove_silence.py
"""Use case: produce a copy of a video with its silent passages removed.

Standalone tool — not part of the reels pipeline (no manifest, no stages).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from reels.application.ports.segment_cutter import SegmentCutter
from reels.application.ports.silence_detector import SilenceDetector
from reels.domain.silence_removal.keep_segments import compute_keep_segments
from reels.domain.source_video.video_prober import VideoProber


class NoAudioTrack(Exception):
    """The video has no audio stream, so silence removal cannot apply."""


@dataclass(frozen=True, slots=True)
class SilenceRemovalSettings:
    threshold_db: float = -35.0
    min_silence: float = 0.6
    padding: float = 0.15


@dataclass(frozen=True, slots=True)
class SilenceRemovalResult:
    original_duration: float
    output_duration: float
    cuts_removed: int


ProgressFn = Callable[[str, str], None]


class RemoveSilence:
    def __init__(
        self, *, prober: VideoProber, detector: SilenceDetector, cutter: SegmentCutter
    ) -> None:
        self._prober = prober
        self._detector = detector
        self._cutter = cutter

    def execute(
        self,
        video_path: Path,
        out_path: Path,
        settings: SilenceRemovalSettings = SilenceRemovalSettings(),
        on_progress: ProgressFn | None = None,
    ) -> SilenceRemovalResult:
        emit: ProgressFn = on_progress or (lambda stage, message: None)

        emit("probe", "reading video metadata")
        meta = self._prober.probe(video_path)
        if not meta.has_audio:
            raise NoAudioTrack("this video has no audio track")

        emit("detect", "detecting silences")
        silences = self._detector.detect(
            video_path,
            threshold_db=settings.threshold_db,
            min_silence=settings.min_silence,
            duration=meta.duration_seconds,
        )
        plan = compute_keep_segments(
            silences,
            meta.duration_seconds,
            min_silence=settings.min_silence,
            padding=settings.padding,
        )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        if plan.cuts_removed == 0:
            shutil.copyfile(video_path, out_path)
            return SilenceRemovalResult(meta.duration_seconds, meta.duration_seconds, 0)

        emit("cut", f"removing {plan.cuts_removed} silent passage(s)")
        self._cutter.cut(video_path, plan.keep_segments, out_path)
        return SilenceRemovalResult(
            original_duration=meta.duration_seconds,
            output_duration=plan.output_duration,
            cuts_removed=plan.cuts_removed,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/application/test_remove_silence.py -v`
Expected: all 4 PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/reels/application tests/application/test_remove_silence.py
git add src/reels/application/ports/silence_detector.py src/reels/application/ports/segment_cutter.py src/reels/application/use_cases/remove_silence.py tests/application/test_remove_silence.py
git commit -m "feat: RemoveSilence use case behind SilenceDetector/SegmentCutter ports

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Infrastructure — FFmpegSilenceDetector

**Files:**
- Create: `src/reels/infrastructure/ffmpeg/ffmpeg_silence_detector.py`
- Test: `tests/infrastructure/test_silencedetect_parser.py`

**Interfaces:**
- Consumes: `SilenceDetector` port (Task 2), `TimeRange`.
- Produces (used by Task 5): `FFmpegSilenceDetector(ffmpeg_path: str | None = None)` implementing the port; module-level `parse_silencedetect(stderr: str, duration: float) -> list[TimeRange]`; `SilenceDetectError(RuntimeError)`.

Important ffmpeg detail: `silencedetect` prints its results at loglevel *info* — the command must NOT pass `-loglevel error` (unlike the other adapters in this directory), or the output disappears.

- [ ] **Step 1: Write the failing tests**

```python
# tests/infrastructure/test_silencedetect_parser.py
"""Parsing ffmpeg silencedetect stderr output."""

from reels.infrastructure.ffmpeg.ffmpeg_silence_detector import parse_silencedetect

# Captured shape of real ffmpeg output: detection lines are interleaved with
# progress/config noise, and values carry varying precision.
SAMPLE = """\
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'input.mp4':
  Duration: 00:00:20.02, start: 0.000000, bitrate: 5157 kb/s
Stream mapping:
  Stream #0:1 -> #0:0 (aac (native) -> pcm_s16le (native))
[silencedetect @ 0x600002a30000] silence_start: 4.51102
[silencedetect @ 0x600002a30000] silence_end: 6.8004 | silence_duration: 2.28938
size=N/A time=00:00:10.00 bitrate=N/A speed= 500x
[silencedetect @ 0x600002a30000] silence_start: 12
[silencedetect @ 0x600002a30000] silence_end: 13.75 | silence_duration: 1.75
size=N/A time=00:00:20.02 bitrate=N/A speed= 480x
"""


def test_parses_start_end_pairs_from_noisy_stderr():
    intervals = parse_silencedetect(SAMPLE, duration=20.02)
    assert [(round(i.start, 3), round(i.end, 3)) for i in intervals] == [
        (4.511, 6.8), (12.0, 13.75),
    ]


def test_trailing_silence_without_end_line_runs_to_file_end():
    stderr = "[silencedetect @ 0x1] silence_start: 18.5\n"
    intervals = parse_silencedetect(stderr, duration=20.0)
    assert [(i.start, i.end) for i in intervals] == [(18.5, 20.0)]


def test_negative_start_from_ffmpeg_is_clamped_to_zero():
    # ffmpeg can report a slightly negative silence_start at the very beginning of a file.
    stderr = (
        "[silencedetect @ 0x1] silence_start: -0.001\n"
        "[silencedetect @ 0x1] silence_end: 2.5 | silence_duration: 2.5\n"
    )
    intervals = parse_silencedetect(stderr, duration=20.0)
    assert [(i.start, i.end) for i in intervals] == [(0.0, 2.5)]


def test_no_detection_lines_yields_no_intervals():
    assert parse_silencedetect("frame= 100 fps= 50\n", duration=20.0) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/infrastructure/test_silencedetect_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'reels.infrastructure.ffmpeg.ffmpeg_silence_detector'`

- [ ] **Step 3: Implement the detector**

```python
# src/reels/infrastructure/ffmpeg/ffmpeg_silence_detector.py
"""FFmpeg silencedetect implementation of the SilenceDetector port."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path

from reels.application.ports.silence_detector import SilenceDetector
from reels.domain.shared.value_objects import TimeRange

logger = logging.getLogger(__name__)

_EPSILON = 1e-3
_START = re.compile(r"silence_start:\s*(-?\d+(?:\.\d+)?)")
_END = re.compile(r"silence_end:\s*(-?\d+(?:\.\d+)?)")


class SilenceDetectError(RuntimeError):
    """The ffmpeg silencedetect pass failed."""


def parse_silencedetect(stderr: str, duration: float) -> list[TimeRange]:
    """Pair silence_start/silence_end lines; an unmatched trailing start runs to the file end."""
    intervals: list[TimeRange] = []
    start: float | None = None
    for line in stderr.splitlines():
        m = _START.search(line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = _END.search(line)
        if m and start is not None:
            end = min(duration, float(m.group(1)))
            if end > start + _EPSILON:
                intervals.append(TimeRange(start, end))
            start = None
    if start is not None and duration > start + _EPSILON:
        intervals.append(TimeRange(start, duration))
    return intervals


class FFmpegSilenceDetector(SilenceDetector):
    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def detect(
        self, video_path: Path, *, threshold_db: float, min_silence: float, duration: float
    ) -> list[TimeRange]:
        # silencedetect logs its results at loglevel info — do not lower the loglevel here.
        cmd = [
            self._ffmpeg, "-hide_banner", "-nostats",
            "-i", str(video_path),
            "-vn", "-af", f"silencedetect=noise={threshold_db}dB:d={min_silence}",
            "-f", "null", "-",
        ]
        logger.info("ffmpeg %s", " ".join(cmd[1:]))
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise SilenceDetectError("ffmpeg binary not found") from exc
        except subprocess.CalledProcessError as exc:
            raise SilenceDetectError(
                f"silence detection failed: {exc.stderr.strip()[-500:]}"
            ) from exc
        return parse_silencedetect(proc.stderr, duration)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/infrastructure/test_silencedetect_parser.py -v`
Expected: all 4 PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/reels/infrastructure/ffmpeg/ffmpeg_silence_detector.py tests/infrastructure/test_silencedetect_parser.py
git add src/reels/infrastructure/ffmpeg/ffmpeg_silence_detector.py tests/infrastructure/test_silencedetect_parser.py
git commit -m "feat: ffmpeg silencedetect adapter with stderr parser

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Infrastructure — FFmpegSegmentCutter

**Files:**
- Create: `src/reels/infrastructure/ffmpeg/ffmpeg_segment_cutter.py`
- Test: `tests/infrastructure/test_segments_filtergraph.py`

**Interfaces:**
- Consumes: `SegmentCutter` port (Task 2), `TimeRange`.
- Produces (used by Task 5): `FFmpegSegmentCutter(ffmpeg_path: str | None = None)` implementing the port; module-level `segments_filtergraph(segments: Sequence[TimeRange]) -> str`; `SegmentCutError(RuntimeError)`.

The filtergraph builder is a pure function tested as a string (same pattern as `tests/infrastructure/test_ending_sound_filtergraph.py`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/infrastructure/test_segments_filtergraph.py
"""The trim+concat filtergraph used to keep only the non-silent segments."""

from reels.domain.shared.value_objects import TimeRange
from reels.infrastructure.ffmpeg.ffmpeg_segment_cutter import segments_filtergraph


def test_two_segments_trim_and_concat_with_reset_timestamps():
    fc = segments_filtergraph([TimeRange(0.0, 4.15), TimeRange(5.85, 10.0)])
    assert fc == (
        "[0:v]trim=start=0.000:end=4.150,setpts=PTS-STARTPTS[v0];"
        "[0:a]atrim=start=0.000:end=4.150,asetpts=PTS-STARTPTS[a0];"
        "[0:v]trim=start=5.850:end=10.000,setpts=PTS-STARTPTS[v1];"
        "[0:a]atrim=start=5.850:end=10.000,asetpts=PTS-STARTPTS[a1];"
        "[v0][a0][v1][a1]concat=n=2:v=1:a=1[vout][aout]"
    )


def test_single_segment_still_concats_to_the_output_labels():
    fc = segments_filtergraph([TimeRange(1.0, 2.0)])
    assert fc.endswith("concat=n=1:v=1:a=1[vout][aout]")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/infrastructure/test_segments_filtergraph.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'reels.infrastructure.ffmpeg.ffmpeg_segment_cutter'`

- [ ] **Step 3: Implement the cutter**

```python
# src/reels/infrastructure/ffmpeg/ffmpeg_segment_cutter.py
"""FFmpeg trim+concat implementation of the SegmentCutter port."""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from reels.application.ports.segment_cutter import SegmentCutter
from reels.domain.shared.value_objects import TimeRange

logger = logging.getLogger(__name__)


class SegmentCutError(RuntimeError):
    """The ffmpeg render pass failed."""


def segments_filtergraph(segments: Sequence[TimeRange]) -> str:
    """Trim each keep-segment (video+audio), reset timestamps, and concat them in order."""
    parts: list[str] = []
    labels = ""
    for i, seg in enumerate(segments):
        span = f"start={seg.start:.3f}:end={seg.end:.3f}"
        parts.append(f"[0:v]trim={span},setpts=PTS-STARTPTS[v{i}]")
        parts.append(f"[0:a]atrim={span},asetpts=PTS-STARTPTS[a{i}]")
        labels += f"[v{i}][a{i}]"
    parts.append(f"{labels}concat=n={len(segments)}:v=1:a=1[vout][aout]")
    return ";".join(parts)


class FFmpegSegmentCutter(SegmentCutter):
    def __init__(self, ffmpeg_path: str | None = None) -> None:
        self._ffmpeg = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"

    def cut(self, video_path: Path, segments: Sequence[TimeRange], out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video_path),
            "-filter_complex", segments_filtergraph(segments),
            "-map", "[vout]", "-map", "[aout]",
            # Quality-preserving defaults: the tool keeps the source's look, not the reels spec.
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ]
        logger.info("ffmpeg cut %d segments -> %s", len(segments), out_path.name)
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise SegmentCutError("ffmpeg binary not found") from exc
        except subprocess.CalledProcessError as exc:
            raise SegmentCutError(f"ffmpeg failed: {exc.stderr.strip()[-500:]}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/infrastructure/test_segments_filtergraph.py -v`
Expected: both PASS

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check src/reels/infrastructure/ffmpeg/ffmpeg_segment_cutter.py tests/infrastructure/test_segments_filtergraph.py
git add src/reels/infrastructure/ffmpeg/ffmpeg_segment_cutter.py tests/infrastructure/test_segments_filtergraph.py
git commit -m "feat: ffmpeg trim+concat segment cutter

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Container wiring, API router, and end-to-end test

**Files:**
- Modify: `src/reels/presentation/container.py` (add `silence_remover` field + wiring)
- Create: `src/reels/presentation/api/routers/silence.py`
- Modify: `src/reels/presentation/api/app.py` (register the router)
- Modify: `pyproject.toml` (dev group: add `httpx`)
- Test: `tests/api/__init__.py` (empty), `tests/api/test_silence_api.py`

**Interfaces:**
- Consumes: `RemoveSilence`, `SilenceRemovalSettings`, `NoAudioTrack` (Task 2); `FullySilentVideo` (Task 1); `FFmpegSilenceDetector` (Task 3); `FFmpegSegmentCutter` (Task 4); existing `JobManager.submit(kind=, video_id=, runner=)` and `Reporter.emit(stage, source_id, message)` from `reels.presentation.api.jobs`; existing SSE endpoint `GET /api/jobs/{job_id}/events`.
- Produces (used by Task 6):
  - `POST /api/silence/jobs` — multipart: `file` (video), form fields `threshold_db`, `min_silence`, `padding` → `{"job_id": str, "token": str}`; `422` for unsupported file type, unreadable video, or video with no audio track.
  - `GET /api/silence/jobs/{token}/result` → `{"original_duration": float, "output_duration": float, "cuts_removed": int, "output_filename": str}`; `404` until the job finishes.
  - `GET /api/silence/jobs/{token}/download` → the output mp4 (`Content-Disposition` filename `<stem>.nosilence.mp4`); `404` until ready.

Files live under `settings.paths.work_dir / "tools" / "silence" / <token>/` — outside the reels pipeline workspace. `token` is a 12-char hex id; reject non-alphanumeric tokens (path-traversal guard). Constructing `FFprobeVideoProber` directly in the router for the early no-audio check follows the existing precedent in `routers/videos.py` (which imports `build_preview`/`build_poster` infra directly).

- [ ] **Step 1: Add the dev dependency and wire the container**

```bash
uv add --group dev httpx
```

In `src/reels/presentation/container.py`:

Add imports (with the other application/infrastructure imports):

```python
from reels.application.use_cases.remove_silence import RemoveSilence
from reels.infrastructure.ffmpeg.ffmpeg_segment_cutter import FFmpegSegmentCutter
from reels.infrastructure.ffmpeg.ffmpeg_silence_detector import FFmpegSilenceDetector
```

Add a field to the `Container` dataclass (after `transcripts: JsonTranscriptRepository`):

```python
    silence_remover: RemoveSilence
```

In `from_settings`, after `editor = FFmpegVideoEditor(...)` (so `ffmpeg_path` is in scope):

```python
        silence_remover = RemoveSilence(
            prober=prober,
            detector=FFmpegSilenceDetector(ffmpeg_path=ffmpeg_path),
            cutter=FFmpegSegmentCutter(ffmpeg_path=ffmpeg_path),
        )
```

And pass `silence_remover=silence_remover` in the final `cls(...)` call.

- [ ] **Step 2: Write the failing end-to-end test**

Create empty `tests/api/__init__.py`, then:

```python
# tests/api/test_silence_api.py
"""End-to-end: upload a video with a silent middle, get back a shorter one."""

import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest

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
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/api/test_silence_api.py -v`
Expected: FAIL — `404` on `POST /api/silence/jobs` (router not registered yet)

- [ ] **Step 4: Implement the router and register it**

```python
# src/reels/presentation/api/routers/silence.py
"""Silence Remover tool endpoints — standalone from the reels pipeline.

Uploads and outputs live under work_dir/tools/silence/<token>/, keyed by a job token.
Progress streams through the existing job SSE endpoint (GET /api/jobs/{job_id}/events).
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from reels.application.use_cases.remove_silence import SilenceRemovalSettings
from reels.infrastructure.ffmpeg.ffprobe_video_prober import FFprobeError, FFprobeVideoProber
from reels.presentation.api.jobs import Reporter
from reels.presentation.api.state import AppState, get_state

router = APIRouter()

StateDep = Annotated[AppState, Depends(get_state)]

_ALLOWED_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


def _tool_dir(state: AppState, token: str) -> Path:
    if not token.isalnum():  # tokens are hex; also guards path traversal
        raise HTTPException(status_code=404, detail="unknown token")
    return state.container.settings.paths.work_dir / "tools" / "silence" / token


@router.post("/silence/jobs")
def start_silence_job(
    state: StateDep,
    file: UploadFile = File(...),
    threshold_db: float = Form(-35.0),
    min_silence: float = Form(0.6),
    padding: float = Form(0.15),
) -> dict[str, str]:
    original = Path(file.filename or "input.mp4")
    suffix = original.suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=422, detail=f"unsupported file type '{suffix}'")

    token = uuid.uuid4().hex[:12]
    workdir = _tool_dir(state, token)
    workdir.mkdir(parents=True, exist_ok=True)
    in_path = workdir / f"input{suffix}"
    with in_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    # Fail fast, before any processing, on files we can't handle (spec: error handling).
    try:
        meta = FFprobeVideoProber().probe(in_path)
    except FFprobeError as exc:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"could not read video: {exc}") from exc
    if not meta.has_audio:
        shutil.rmtree(workdir, ignore_errors=True)
        raise HTTPException(status_code=422, detail="this video has no audio track")

    out_path = workdir / f"{original.stem}.nosilence.mp4"
    settings = SilenceRemovalSettings(
        threshold_db=threshold_db, min_silence=min_silence, padding=padding
    )
    remover = state.container.silence_remover

    def runner(reporter: Reporter) -> None:
        result = remover.execute(
            in_path,
            out_path,
            settings,
            on_progress=lambda stage, message: reporter.emit(stage, token, message),
        )
        (workdir / "result.json").write_text(
            json.dumps(
                {
                    "original_duration": result.original_duration,
                    "output_duration": result.output_duration,
                    "cuts_removed": result.cuts_removed,
                    "output_filename": out_path.name,
                }
            ),
            encoding="utf-8",
        )
        reporter.emit("done", token, "silence removal complete")

    job = state.jobs.submit(kind="silence", video_id=token, runner=runner)
    return {"job_id": job.id, "token": token}


@router.get("/silence/jobs/{token}/result")
def silence_result(token: str, state: StateDep) -> dict[str, Any]:
    path = _tool_dir(state, token) / "result.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="result not ready")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/silence/jobs/{token}/download")
def silence_download(token: str, state: StateDep) -> FileResponse:
    workdir = _tool_dir(state, token)
    result = workdir / "result.json"
    if not result.exists():
        raise HTTPException(status_code=404, detail="output not ready")
    name = json.loads(result.read_text(encoding="utf-8"))["output_filename"]
    out = workdir / name
    if not out.exists():
        raise HTTPException(status_code=404, detail="output file missing")
    return FileResponse(out, media_type="video/mp4", filename=name)
```

In `src/reels/presentation/api/app.py`, change the router import/registration block to:

```python
    from .routers import jobs, silence, system, videos

    app.include_router(system.router, prefix="/api", tags=["system"])
    app.include_router(videos.router, prefix="/api", tags=["videos"])
    app.include_router(jobs.router, prefix="/api", tags=["jobs"])
    app.include_router(silence.router, prefix="/api", tags=["silence"])
```

Note: `NoAudioTrack` and `FullySilentVideo` raised inside the runner surface via the existing `JobManager` failure path (`job.state == "failed"`, `job.error` = message) — the UI shows them; no extra handling needed in the router.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/api/test_silence_api.py -v`
Expected: both PASS (or SKIP if ffmpeg is absent — on this machine it is present)

- [ ] **Step 6: Run the full suite, lint, and commit**

```bash
uv run pytest
uv run ruff check src tests
git add pyproject.toml uv.lock src/reels/presentation tests/api
git commit -m "feat: silence-removal API endpoints on the background job manager

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Web UI — Silence Remover tab

**Files:**
- Modify: `web/src/lib/api.ts` (types + client functions)
- Create: `web/src/components/SilenceRemover.tsx`
- Modify: `web/src/App.tsx` (new tab)

**Interfaces:**
- Consumes: Task 5's endpoints; existing `subscribeJob(jobId, {onProgress, onEnd})` and `fmtClock(s)` from `web/src/lib/api.ts`.
- Produces: a "Silence" tab in the app nav rendering `<SilenceRemover />`.

- [ ] **Step 1: Add API client functions**

Append to `web/src/lib/api.ts`:

```ts
// --- Silence Remover tool (standalone from the reels pipeline) ---

export type SilenceResult = {
  original_duration: number;
  output_duration: number;
  cuts_removed: number;
  output_filename: string;
};

export type SilenceSettings = {
  threshold_db: number;
  min_silence: number;
  padding: number;
};

export const SILENCE_DEFAULTS: SilenceSettings = {
  threshold_db: -35,
  min_silence: 0.6,
  padding: 0.15,
};

export async function removeSilence(
  file: File,
  settings: SilenceSettings,
): Promise<{ job_id: string; token: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("threshold_db", String(settings.threshold_db));
  form.append("min_silence", String(settings.min_silence));
  form.append("padding", String(settings.padding));
  // No Content-Type header: the browser sets the multipart boundary.
  const res = await fetch("/api/silence/jobs", { method: "POST", body: form });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return res.json();
}

export const getSilenceResult = (token: string) =>
  http<SilenceResult>(`/silence/jobs/${encodeURIComponent(token)}/result`);

export const silenceDownloadUrl = (token: string) =>
  `/api/silence/jobs/${encodeURIComponent(token)}/download`;
```

- [ ] **Step 2: Create the component**

```tsx
// web/src/components/SilenceRemover.tsx
import { useRef, useState } from "react";
import { Download, Loader2, Scissors } from "lucide-react";
import {
  fmtClock,
  getSilenceResult,
  removeSilence,
  SILENCE_DEFAULTS,
  silenceDownloadUrl,
  subscribeJob,
  type SilenceResult,
  type SilenceSettings,
} from "../lib/api";

type Phase = "idle" | "running" | "done" | "failed";

const FIELDS: {
  key: keyof SilenceSettings;
  label: string;
  hint: string;
  step: number;
}[] = [
  { key: "threshold_db", label: "Silence threshold (dB)", hint: "Audio below this level counts as silence", step: 1 },
  { key: "min_silence", label: "Min silence (s)", hint: "Shorter quiet gaps are left alone", step: 0.1 },
  { key: "padding", label: "Edge padding (s)", hint: "Audio kept on each side of a cut", step: 0.05 },
];

export function SilenceRemover() {
  const [file, setFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<SilenceSettings>(SILENCE_DEFAULTS);
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [result, setResult] = useState<SilenceResult | null>(null);
  const cleanup = useRef<(() => void) | null>(null);

  async function start() {
    if (!file) return;
    setPhase("running");
    setError(null);
    setResult(null);
    setMessage("uploading…");
    try {
      const { job_id, token } = await removeSilence(file, settings);
      setToken(token);
      cleanup.current = subscribeJob(job_id, {
        onProgress: (e) => setMessage(`${e.stage}: ${e.message}`),
        onEnd: async (state, err) => {
          if (state === "done") {
            setResult(await getSilenceResult(token));
            setPhase("done");
          } else {
            setError(err ?? "processing failed");
            setPhase("failed");
          }
        },
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("failed");
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">Silence Remover</h1>
        <p className="text-sm text-muted-foreground">
          Upload a video and get back a copy with the silent passages cut out. Separate from
          the reels pipeline.
        </p>
      </div>

      <label className="block cursor-pointer rounded-xl border-2 border-dashed border-border p-8 text-center transition hover:border-primary/50">
        <input
          type="file"
          accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <span className="text-sm font-medium">{file.name}</span>
        ) : (
          <span className="text-sm text-muted-foreground">Click to choose a video file</span>
        )}
      </label>

      <div className="grid grid-cols-3 gap-4">
        {FIELDS.map((f) => (
          <label key={f.key} className="space-y-1 text-sm" title={f.hint}>
            <span className="text-muted-foreground">{f.label}</span>
            <input
              type="number"
              step={f.step}
              value={settings[f.key]}
              onChange={(e) =>
                setSettings({ ...settings, [f.key]: Number(e.target.value) })
              }
              className="w-full rounded-md border border-border bg-background px-2 py-1.5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            />
          </label>
        ))}
      </div>

      <button
        onClick={start}
        disabled={!file || phase === "running"}
        className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
      >
        {phase === "running" ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Scissors className="size-4" />
        )}
        Remove silence
      </button>

      {phase === "running" && (
        <p className="text-sm text-muted-foreground">{message}</p>
      )}
      {phase === "failed" && error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}
      {phase === "done" && result && token && (
        <div className="space-y-3 rounded-xl border border-border p-4">
          {result.cuts_removed === 0 ? (
            <p className="text-sm">No silence found — the output equals the input.</p>
          ) : (
            <p className="text-sm">
              Removed <strong>{result.cuts_removed}</strong> silent passage
              {result.cuts_removed === 1 ? "" : "s"}:{" "}
              {fmtClock(result.original_duration)} → {fmtClock(result.output_duration)}
            </p>
          )}
          <a
            href={silenceDownloadUrl(token)}
            download={result.output_filename}
            className="inline-flex items-center gap-2 rounded-lg bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition hover:bg-secondary/80"
          >
            <Download className="size-4" />
            Download {result.output_filename}
          </a>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add the tab in App.tsx**

In `web/src/App.tsx`:

- Add the import: `import { SilenceRemover } from "./components/SilenceRemover";`
- Change the Tab type: `type Tab = "library" | "gallery" | "silence" | "config" | "health";`
- Change the nav array literal to `(["library", "gallery", "silence", "config", "health"] as Tab[])`
- Add to the `<main>` block (alongside the other tab renders): `{tab === "silence" && <SilenceRemover />}`

- [ ] **Step 4: Typecheck/build the frontend**

```bash
cd web && npm run build
```

Expected: build succeeds with no TypeScript errors. (If `npm run build` is not a defined script, run `npx tsc -b && npx vite build`.)

- [ ] **Step 5: Manual smoke test**

Start the API (`uv run uvicorn` per README / `reels` web entry) and the Vite dev server, open the Silence tab, upload a short clip with pauses, verify progress messages stream, stats appear, and the download plays with silences removed.

- [ ] **Step 6: Commit and close out**

```bash
git add web/src
git commit -m "feat: Silence Remover tab in Reels Studio

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
bd close rg-7ol
```

---

## Self-Review Notes

- Spec coverage: domain math (T1), ports/use case (T2), detector (T3), cutter (T4), API + jobs + storage + error handling (T5), UI + defaults + stats (T6). "No silence found" path covered in T2 (copy) and T6 (UI note). "No audio" covered in T2 (use case guard) and T5 (early 422). "Fully silent" covered in T1 (domain error) and surfaces via the job error path (T5 note).
- The spec's `SilenceInterval`/`KeepSegment` value objects are realized as the shared-kernel `TimeRange` (identical invariants; avoids duplicate interval types). The spec's intent — validated immutable intervals — is preserved.
