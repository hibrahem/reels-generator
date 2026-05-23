"""ClipSelector backed by the Anthropic (Claude) Messages API.

Same contract as the OpenAI-compatible selector; Claude takes the system prompt as a top-level
parameter and returns content blocks. Retries once on malformed JSON (spec §5.3).
"""

from __future__ import annotations

import logging

from reels.domain.reel.clip_selection import ClipCandidate
from reels.domain.reel.clip_selector import ClipSelector, SelectionConstraints
from reels.domain.transcript.transcript import Transcript

from .clip_json import MalformedSelectionResponse, parse_clip_candidates
from .prompts import SELECTION_SYSTEM, build_user_prompt

logger = logging.getLogger(__name__)


class ClaudeClipSelector(ClipSelector):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        temperature: float = 0.2,
        max_retries: int = 1,
        max_tokens: int = 4096,
    ) -> None:
        from anthropic import Anthropic

        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._max_tokens = max_tokens

    def select_clips(
        self, transcript: Transcript, constraints: SelectionConstraints
    ) -> list[ClipCandidate]:
        user_prompt = build_user_prompt(transcript, constraints)
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            content = self._complete(user_prompt)
            try:
                return parse_clip_candidates(content)
            except MalformedSelectionResponse as exc:
                last_error = exc
                logger.warning("selection JSON malformed (attempt %d): %s", attempt + 1, exc)
        raise MalformedSelectionResponse(
            f"could not parse selection response after {self._max_retries + 1} attempts: "
            f"{last_error}"
        )

    def _complete(self, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system=SELECTION_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")
