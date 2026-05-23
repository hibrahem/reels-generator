"""OpenCV (Haar cascade) implementation of the PresenterDetector port (spec §6).

Samples frames across the clip, finds the presenter's face, and reports a stable bounding box plus a
stability score. Degrades gracefully: if detection is sparse or jumpy it returns a low-stability /
empty result so the caller falls back to an anchor crop and flags the reel — it never crashes.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from reels.domain.reel.layout_plan import PresenterDetection
from reels.domain.reel.presenter_detector import PresenterDetector
from reels.domain.shared.value_objects import CropRectangle, TimeRange

logger = logging.getLogger(__name__)

_DETECT_WIDTH = 960  # downscale frames to this width for faster detection
_MAX_SAMPLES = 20
_MIN_DETECTION_RATE = 0.4  # need faces in at least this fraction of sampled frames


class OpenCVPresenterDetector(PresenterDetector):
    def __init__(self) -> None:
        import cv2

        self._cv2 = cv2
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self._cascade = cv2.CascadeClassifier(cascade_path)

    def detect(
        self, video_path: Path, span: TimeRange, sample_interval_seconds: float
    ) -> PresenterDetection:
        cv2 = self._cv2
        cap = cv2.VideoCapture(str(video_path))
        try:
            timestamps = self._sample_timestamps(span, sample_interval_seconds)
            boxes: list[tuple[int, int, int, int]] = []  # full-res x,y,w,h of the largest face
            for t in timestamps:
                cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                face = self._largest_face(frame)
                if face is not None:
                    boxes.append(face)
            return self._summarize(boxes, sampled=len(timestamps))
        finally:
            cap.release()

    def _sample_timestamps(self, span: TimeRange, interval: float) -> list[float]:
        interval = max(interval, 0.5)
        n = min(int(span.duration / interval) + 1, _MAX_SAMPLES)
        if n <= 1:
            return [span.start + span.duration / 2.0]
        step = span.duration / (n - 1)
        return [span.start + i * step for i in range(n)]

    def _largest_face(self, frame) -> tuple[int, int, int, int] | None:
        cv2 = self._cv2
        h, w = frame.shape[:2]
        scale = w / _DETECT_WIDTH if w > _DETECT_WIDTH else 1.0
        small = cv2.resize(frame, (int(w / scale), int(h / scale))) if scale != 1.0 else frame
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(48, 48)
        )
        if len(faces) == 0:
            return None
        fx, fy, fw, fh = max(faces, key=lambda b: b[2] * b[3])  # largest by area
        return (int(fx * scale), int(fy * scale), int(fw * scale), int(fh * scale))

    def _summarize(self, boxes: list, sampled: int) -> PresenterDetection:
        if sampled == 0 or not boxes:
            return PresenterDetection(box=None, stability=0.0, sampled_frames=sampled)

        arr = np.array(boxes, dtype=float)
        median = np.median(arr, axis=0)
        mx, my, mw, mh = (int(round(v)) for v in median)
        box = CropRectangle(x=max(mx, 0), y=max(my, 0), width=max(mw, 1), height=max(mh, 1))

        detection_rate = len(boxes) / sampled
        centers_x = arr[:, 0] + arr[:, 2] / 2.0
        frame_spread = float(np.std(centers_x))
        # Tight clustering of face centers → high positional stability.
        positional = max(0.0, 1.0 - frame_spread / (mw * 2.0 + 1.0))
        stability = (detection_rate if detection_rate >= _MIN_DETECTION_RATE else 0.0) * positional
        logger.info(
            "presenter detection: %d/%d frames, rate=%.2f, spread=%.0fpx, stability=%.2f",
            len(boxes),
            sampled,
            detection_rate,
            frame_spread,
            stability,
        )
        return PresenterDetection(box=box, stability=round(stability, 3), sampled_frames=sampled)
