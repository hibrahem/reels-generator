"""Pydantic response models for the web API + converters from domain objects."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from pydantic import BaseModel, Field

from reels.application.manifest import Manifest
from reels.application.queries.video_queries import VideoSummary
from reels.domain.reel.reel import Reel
from reels.domain.transcript.transcript import Segment, Word


class VideoSummaryOut(BaseModel):
    id: str
    filename: str
    ingested: bool
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool | None
    completed_stages: list[str]
    reel_count: int
    warning_count: int

    @classmethod
    def of(cls, s: VideoSummary) -> VideoSummaryOut:
        return cls(**dataclasses.asdict(s))


class ReelOut(BaseModel):
    index: int
    start: float
    end: float
    duration: float
    title: str
    hook: str
    caption: str
    reason: str
    confidence: float
    visual_dependent: bool
    mode: str | None
    output_filename: str
    stages: dict[str, bool]
    # mtime of the rendered file the media endpoint serves; the UI appends it to the media URL
    # so a re-rendered reel gets a fresh URL instead of the browser's cached copy.
    rendered_at: float | None

    @classmethod
    def of(cls, reel: Reel, output_dir: Path) -> ReelOut:
        c = reel.candidate
        packaged = (output_dir / reel.output_filename()).exists()
        rendered = output_dir / reel.output_filename() if packaged else reel.final_path
        return cls(
            index=reel.index,
            start=c.time_range.start,
            end=c.time_range.end,
            duration=c.time_range.duration,
            title=c.title,
            hook=c.hook,
            caption=c.caption,
            reason=c.reason,
            confidence=float(c.confidence),
            visual_dependent=c.visual_dependent,
            mode=reel.mode.value if reel.mode else None,
            output_filename=reel.output_filename(),
            rendered_at=rendered.stat().st_mtime
            if rendered is not None and rendered.exists()
            else None,
            stages={
                "plan-layout": reel.layout is not None,
                "cut": reel.cut_path is not None,
                "reframe": reel.reframed_path is not None,
                "caption": reel.captioned_path is not None,
                "brand": reel.final_path is not None,
                "package": packaged,
            },
        )


class VideoDetailOut(BaseModel):
    id: str
    filename: str
    ingested: bool
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    has_audio: bool | None
    transcript_available: bool
    completed_stages: list[str]
    warnings: list[str]
    reels: list[ReelOut]

    @classmethod
    def of(cls, m: Manifest, output_dir: Path) -> VideoDetailOut:
        meta = m.source.metadata
        return cls(
            id=m.source.id.value,
            filename=m.source.path.name,
            ingested=meta is not None,
            duration_seconds=meta.duration_seconds if meta else None,
            width=meta.resolution.width if meta else None,
            height=meta.resolution.height if meta else None,
            fps=meta.fps if meta else None,
            has_audio=meta.has_audio if meta else None,
            transcript_available=m.transcript_path is not None,
            completed_stages=[s.value for s in m.completed_stages],
            warnings=m.warnings,
            reels=[ReelOut.of(r, output_dir) for r in m.reels],
        )


class WordIn(BaseModel):
    """One edited word from the client. `text` may change; `start`/`end` must be preserved."""

    text: str
    start: float
    end: float
    probability: float | None = None

    def to_domain(self) -> Word:
        return Word(
            text=self.text, start=self.start, end=self.end, probability=self.probability
        )


class SegmentIn(BaseModel):
    """One edited segment with its words. Timings carry through unchanged; only text is edited."""

    text: str
    start: float
    end: float
    words: list[WordIn] = Field(default_factory=list)

    def to_domain(self) -> Segment:
        return Segment(
            text=self.text,
            start=self.start,
            end=self.end,
            words=tuple(w.to_domain() for w in self.words),
        )


class TranscriptEditIn(BaseModel):
    """Body for PATCH /videos/{id}/transcript — the full edited segment list."""

    segments: list[SegmentIn]

    def to_domain_segments(self) -> list[Segment]:
        return [s.to_domain() for s in self.segments]


class DoctorCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class DoctorOut(BaseModel):
    checks: list[DoctorCheck]
