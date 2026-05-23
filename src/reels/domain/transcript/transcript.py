"""The Transcript entity and its constituent value objects.

The whole pipeline keys off word-level timestamps, so this model treats words as first-class.
Arabic word timing from Whisper is known to drift; nothing here assumes perfection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from reels.domain.shared.exceptions import EmptyTranscript


@dataclass(frozen=True, slots=True)
class Word:
    """A single transcribed word with its timing."""

    text: str
    start: float
    end: float
    probability: float | None = None

    @property
    def midpoint(self) -> float:
        return (self.start + self.end) / 2.0


@dataclass(frozen=True, slots=True)
class Segment:
    """A contiguous run of speech as emitted by the transcriber, with its words."""

    text: str
    start: float
    end: float
    words: tuple[Word, ...] = field(default_factory=tuple)


@dataclass(slots=True)
class Transcript:
    """A timestamped transcript of one source video.

    Identity is the source video it belongs to; equality is not value-based here because two
    transcribe runs of the same source are still "the transcript of that source".
    """

    source_id: str
    language: str
    duration_seconds: float
    segments: tuple[Segment, ...]

    @property
    def words(self) -> list[Word]:
        """Flattened, time-ordered list of every word across all segments."""
        flat = [w for segment in self.segments for w in segment.words]
        flat.sort(key=lambda w: w.start)
        return flat

    @property
    def full_text(self) -> str:
        return " ".join(segment.text.strip() for segment in self.segments).strip()

    def has_words(self) -> bool:
        return any(segment.words for segment in self.segments)

    def snap_start_to_word_boundary(self, t: float) -> float:
        """Snap a proposed clip start to the start of the nearest word at/after the boundary."""
        words = self._require_words()
        # Prefer the first word whose start is at or after t; fall back to the closest by start.
        candidates = [w for w in words if w.start >= t - 0.25]
        chosen = candidates[0] if candidates else min(words, key=lambda w: abs(w.start - t))
        return chosen.start

    def snap_end_to_word_boundary(self, t: float) -> float:
        """Snap a proposed clip end to the end of the nearest word at/before the boundary."""
        words = self._require_words()
        candidates = [w for w in words if w.end <= t + 0.25]
        chosen = candidates[-1] if candidates else min(words, key=lambda w: abs(w.end - t))
        return chosen.end

    def words_within(self, start: float, end: float) -> list[Word]:
        """Words whose midpoint falls inside [start, end] — the words spoken during a clip."""
        return [w for w in self.words if start <= w.midpoint <= end]

    def _require_words(self) -> list[Word]:
        words = self.words
        if not words:
            raise EmptyTranscript("transcript has no word-level timings to snap against")
        return words
