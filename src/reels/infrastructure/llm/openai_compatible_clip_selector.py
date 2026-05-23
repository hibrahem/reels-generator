"""ClipSelector backed by any OpenAI-compatible Chat Completions API (OpenAI or DeepSeek).

Only differs per provider by base_url, API key, and model — supplied by the composition root.
Uses JSON output mode, strips fences defensively, and retries once on malformed JSON (spec §5.3).
"""

from __future__ import annotations

import logging

from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.clip_selector import ClipSelector, SelectionConstraints
from reels.domain.transcript.transcript import Transcript

from .clip_json import MalformedSelectionResponse, parse_clip_candidates
from .prompts import SELECTION_SYSTEM, build_user_prompt

logger = logging.getLogger(__name__)


class OpenAICompatibleClipSelector(ClipSelector):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_retries: int = 1,
    ) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries

    def select_clips(
        self, transcript: Transcript, constraints: SelectionConstraints
    ) -> list[ClipCandidate]:
        messages = [
            {"role": "system", "content": SELECTION_SYSTEM},
            {"role": "user", "content": build_user_prompt(transcript, constraints)},
        ]
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            content = self._complete(messages)
            try:
                return parse_clip_candidates(content)
            except MalformedSelectionResponse as exc:
                last_error = exc
                logger.warning("selection JSON malformed (attempt %d): %s", attempt + 1, exc)
        raise MalformedSelectionResponse(
            f"could not parse selection response after {self._max_retries + 1} attempts: "
            f"{last_error}"
        )

    def _complete(self, messages: list[dict]) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
