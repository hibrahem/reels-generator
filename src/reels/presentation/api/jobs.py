"""A small background-job manager for the web layer.

Pipeline stages are CPU-bound (transcription, ffmpeg), so jobs run on a single worker thread (one
at a time) and report coarse per-stage progress. The SSE endpoint polls the job's event list — no
async/thread queue bridging needed.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class JobEvent:
    stage: str
    source_id: str
    message: str
    ts: float


class Reporter:
    """Passed to a job runner so it can emit progress events."""

    def __init__(self, job: Job) -> None:
        self._job = job

    def emit(self, stage: str, source_id: str, message: str) -> None:
        self._job.push(JobEvent(stage=stage, source_id=source_id, message=message, ts=time.time()))


@dataclass
class Job:
    id: str
    kind: str  # "pipeline" | "reel" | "preview"
    video_id: str
    from_stage: str | None = None
    to_stage: str | None = None
    reel_indices: list[int] | None = None
    state: str = "queued"  # queued | running | done | failed
    error: str | None = None
    created: float = field(default_factory=time.time)
    _events: list[JobEvent] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def push(self, event: JobEvent) -> None:
        with self._lock:
            self._events.append(event)

    def events(self) -> list[JobEvent]:
        with self._lock:
            return list(self._events)


class JobManager:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reels-job")
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        *,
        kind: str,
        video_id: str,
        runner: Callable[[Reporter], None],
        from_stage: str | None = None,
        to_stage: str | None = None,
        reel_indices: list[int] | None = None,
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:12],
            kind=kind,
            video_id=video_id,
            from_stage=from_stage,
            to_stage=to_stage,
            reel_indices=reel_indices,
        )
        with self._lock:
            self._jobs[job.id] = job
        self._executor.submit(self._run, job, runner)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self, video_id: str | None = None) -> list[Job]:
        jobs = sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)
        return [j for j in jobs if video_id is None or j.video_id == video_id]

    def _run(self, job: Job, runner: Callable[[Reporter], None]) -> None:
        job.state = "running"
        try:
            runner(Reporter(job))
            job.state = "done"
        except Exception as exc:  # noqa: BLE001 — surface any failure to the UI
            logger.exception("job %s failed", job.id)
            job.state = "failed"
            job.error = str(exc)
            job.push(JobEvent("error", job.video_id, str(exc), time.time()))
