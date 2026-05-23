"""Defensive parsing of an LLM's JSON clip response into domain ClipCandidates.

Strips code fences before parsing (spec §5.3). Skips individual malformed items rather than failing
the whole batch, since the domain reconciliation step will still validate what survives.
"""

from __future__ import annotations

import json
import logging
import re

from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.shared.exceptions import DomainError
from reels.domain.shared.value_objects import Confidence, TimeRange

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


class MalformedSelectionResponse(ValueError):
    """The LLM response could not be parsed as the expected JSON object."""


def strip_code_fences(text: str) -> str:
    return _FENCE.sub("", text.strip()).strip()


def parse_clip_candidates(content: str) -> list[ClipCandidate]:
    """Parse a ``{"clips": [...]}`` response. Raises on unparseable JSON; skips bad items."""
    cleaned = strip_code_fences(content)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise MalformedSelectionResponse(str(exc)) from exc

    raw_clips = payload.get("clips") if isinstance(payload, dict) else payload
    if not isinstance(raw_clips, list):
        raise MalformedSelectionResponse("expected a 'clips' array in the response")

    candidates: list[ClipCandidate] = []
    for item in raw_clips:
        candidate = _to_candidate(item)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _to_candidate(item: object) -> ClipCandidate | None:
    if not isinstance(item, dict):
        return None
    try:
        time_range = TimeRange(start=float(item["start"]), end=float(item["end"]))
        confidence = Confidence(_clamp01(float(item.get("confidence", 0.5))))
    except (KeyError, TypeError, ValueError, DomainError) as exc:
        logger.warning("skipping malformed clip %r: %s", item, exc)
        return None
    return ClipCandidate(
        time_range=time_range,
        title=str(item.get("title", "")).strip() or "clip",
        hook=str(item.get("hook", "")).strip(),
        caption=str(item.get("caption", "")).strip(),
        reason=str(item.get("reason", "")).strip(),
        confidence=confidence,
        visual_dependent=bool(item.get("visual_dependent", False)),
    )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
