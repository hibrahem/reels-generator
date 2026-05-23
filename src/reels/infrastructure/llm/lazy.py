"""A ClipSelector that defers building the real provider client until selection actually runs.

This keeps ingest/transcribe runs from requiring an LLM API key just to construct the pipeline; the
provider (and its key check) is only resolved when the select stage executes.
"""

from __future__ import annotations

from collections.abc import Callable

from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.clip_selector import ClipSelector, SelectionConstraints
from reels.domain.transcript.transcript import Transcript


class LazyClipSelector(ClipSelector):
    def __init__(self, factory: Callable[[], ClipSelector]) -> None:
        self._factory = factory
        self._delegate: ClipSelector | None = None

    def select_clips(
        self, transcript: Transcript, constraints: SelectionConstraints
    ) -> list[ClipCandidate]:
        if self._delegate is None:
            self._delegate = self._factory()
        return self._delegate.select_clips(transcript, constraints)
