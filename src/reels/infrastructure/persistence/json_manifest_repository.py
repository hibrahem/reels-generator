"""JSON persistence of the per-video manifest.

Maps the in-memory :class:`Manifest` (domain aggregates + pipeline state) to/from a JSON document
stored at ``<working_dir>/manifest.json``. Domain objects stay free of serialization concerns;
all the mapping lives here in infrastructure.
"""

from __future__ import annotations

import json
from pathlib import Path

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.layout_plan import LayoutPlan, ReframeMode
from reels.domain.reel.reel import Reel
from reels.domain.shared.value_objects import Confidence, CropRectangle, Resolution, TimeRange
from reels.domain.source_video.source_video import SourceVideo, SourceVideoId
from reels.domain.source_video.video_metadata import VideoMetadata

MANIFEST_FILENAME = "manifest.json"


class JsonManifestRepository(ManifestRepository):
    def __init__(self, work_root: Path) -> None:
        self._work_root = work_root

    def load(self, source_id: str) -> Manifest | None:
        path = self._work_root / source_id / MANIFEST_FILENAME
        if not path.exists():
            return None
        return _manifest_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, manifest: Manifest) -> None:
        working_dir = manifest.source.working_dir
        working_dir.mkdir(parents=True, exist_ok=True)
        path = working_dir / MANIFEST_FILENAME
        path.write_text(
            json.dumps(_manifest_to_dict(manifest), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_all(self) -> list[Manifest]:
        if not self._work_root.exists():
            return []
        manifests = []
        for path in sorted(self._work_root.glob(f"*/{MANIFEST_FILENAME}")):
            manifests.append(_manifest_from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return manifests


# --- mapping -----------------------------------------------------------------------------------


def _manifest_to_dict(m: Manifest) -> dict:
    return {
        "source": _source_to_dict(m.source),
        "transcript_path": str(m.transcript_path) if m.transcript_path else None,
        "completed_stages": [s.value for s in m.completed_stages],
        "warnings": m.warnings,
        "reels": [_reel_to_dict(r) for r in m.reels],
    }


def _manifest_from_dict(data: dict) -> Manifest:
    transcript_path = data.get("transcript_path")
    source = _source_from_dict(data["source"])
    return Manifest(
        source=source,
        transcript_path=Path(transcript_path) if transcript_path else None,
        completed_stages=[Stage(s) for s in data.get("completed_stages", [])],
        warnings=list(data.get("warnings", [])),
        reels=[_reel_from_dict(r, source.id.value) for r in data.get("reels", [])],
    )


def _source_to_dict(source: SourceVideo) -> dict:
    meta = source.metadata
    return {
        "id": source.id.value,
        "path": str(source.path),
        "working_dir": str(source.working_dir),
        "metadata": None
        if meta is None
        else {
            "duration_seconds": meta.duration_seconds,
            "width": meta.resolution.width,
            "height": meta.resolution.height,
            "fps": meta.fps,
            "has_audio": meta.has_audio,
            "video_codec": meta.video_codec,
            "audio_codec": meta.audio_codec,
        },
    }


def _source_from_dict(data: dict) -> SourceVideo:
    meta = data.get("metadata")
    metadata = None
    if meta is not None:
        metadata = VideoMetadata(
            duration_seconds=meta["duration_seconds"],
            resolution=Resolution(width=meta["width"], height=meta["height"]),
            fps=meta["fps"],
            has_audio=meta["has_audio"],
            video_codec=meta.get("video_codec"),
            audio_codec=meta.get("audio_codec"),
        )
    return SourceVideo(
        id=SourceVideoId(data["id"]),
        path=Path(data["path"]),
        working_dir=Path(data["working_dir"]),
        metadata=metadata,
    )


def _reel_to_dict(reel: Reel) -> dict:
    c = reel.candidate
    return {
        "index": reel.index,
        "candidate": {
            "start": c.time_range.start,
            "end": c.time_range.end,
            "title": c.title,
            "hook": c.hook,
            "caption": c.caption,
            "reason": c.reason,
            "confidence": float(c.confidence),
            "visual_dependent": c.visual_dependent,
        },
        "layout": _layout_to_dict(reel.layout),
        "cut_path": _opt_str(reel.cut_path),
        "reframed_path": _opt_str(reel.reframed_path),
        "captioned_path": _opt_str(reel.captioned_path),
        "final_path": _opt_str(reel.final_path),
        "warnings": reel.warnings,
    }


def _reel_from_dict(data: dict, source_id: str) -> Reel:
    c = data["candidate"]
    candidate = ClipCandidate(
        time_range=TimeRange(start=c["start"], end=c["end"]),
        title=c["title"],
        hook=c["hook"],
        caption=c["caption"],
        reason=c["reason"],
        confidence=Confidence(c["confidence"]),
        visual_dependent=c.get("visual_dependent", False),
    )
    reel = Reel(source_id=source_id, index=data["index"], candidate=candidate)
    reel.layout = _layout_from_dict(data.get("layout"))
    reel.cut_path = _opt_path(data.get("cut_path"))
    reel.reframed_path = _opt_path(data.get("reframed_path"))
    reel.captioned_path = _opt_path(data.get("captioned_path"))
    reel.final_path = _opt_path(data.get("final_path"))
    reel.warnings = list(data.get("warnings", []))
    return reel


def _layout_to_dict(layout: LayoutPlan | None) -> dict | None:
    if layout is None:
        return None
    return {
        "mode": layout.mode.value,
        "presenter_crop": _crop_to_dict(layout.presenter_crop),
        "slide_crop": _crop_to_dict(layout.slide_crop) if layout.slide_crop else None,
        "fallback_used": layout.fallback_used,
        "warnings": list(layout.warnings),
    }


def _layout_from_dict(data: dict | None) -> LayoutPlan | None:
    if data is None:
        return None
    slide = data.get("slide_crop")
    return LayoutPlan(
        mode=ReframeMode(data["mode"]),
        presenter_crop=_crop_from_dict(data["presenter_crop"]),
        slide_crop=_crop_from_dict(slide) if slide else None,
        fallback_used=data.get("fallback_used", False),
        warnings=tuple(data.get("warnings", [])),
    )


def _crop_to_dict(crop: CropRectangle) -> dict:
    return {"x": crop.x, "y": crop.y, "width": crop.width, "height": crop.height}


def _crop_from_dict(data: dict) -> CropRectangle:
    return CropRectangle(x=data["x"], y=data["y"], width=data["width"], height=data["height"])


def _opt_str(p: Path | None) -> str | None:
    return str(p) if p else None


def _opt_path(s: str | None) -> Path | None:
    return Path(s) if s else None
