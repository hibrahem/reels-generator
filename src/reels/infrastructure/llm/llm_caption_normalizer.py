"""LLM-backed CaptionNormalizer (OpenAI-compatible / DeepSeek, or Claude).

One call per video maps transliterated-English tokens to Latin. Token-keyed JSON output, so word
order and timings are untouched; unknown/Arabic tokens are simply left out of the map.
"""

from __future__ import annotations

import json
import logging

from reels.application.ports.caption_normalizer import CaptionNormalizer

from .clip_json import strip_code_fences

logger = logging.getLogger(__name__)

_SYSTEM = """You normalize words from an Egyptian-Arabic software lecture transcript.
You receive a JSON array of word tokens. Some are English technical terms transliterated into
Arabic letters (e.g. "كوبلينج"=Coupling, "ديتابيز"/"داتابيز"=Database, "سيرفيس"=Service,
"ويرهاوس"=Warehouse, "ريكوست"=Request, "ريسبونس"=Response, "كود"=Code, "ديتا"/"داتا"=Data,
"سيستم"=System, "ميثود"=Method, "كلاس"=Class, "موديول"=Module).

Return a JSON object mapping ONLY those tokens to their correct English/Latin spelling. Rules:
- If a token has the Arabic definite article "ال" attached (e.g. "الكوبلينج"), map it to
  "الـ Coupling" — keep the article as "الـ" then a space then the Latin word.
- Leave out purely-Arabic words and tokens that are already Latin.
- Preserve any trailing/leading characters' intent; map the whole token.
Return ONLY the JSON object, e.g. {"الكوبلينج":"الـ Coupling","ديتابيز":"Database"}."""


class LLMCaptionNormalizer(CaptionNormalizer):
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        openai_compatible: bool = True,
        temperature: float = 0.0,
        max_retries: int = 1,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._openai_compatible = openai_compatible
        if openai_compatible:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=api_key)

    def normalize(self, tokens: list[str]) -> dict[str, str]:
        if not tokens:
            return {}
        user = json.dumps(sorted(set(tokens)), ensure_ascii=False)
        for attempt in range(self._max_retries + 1):
            try:
                content = self._complete(user)
                payload = json.loads(strip_code_fences(content))
                if isinstance(payload, dict):
                    return {str(k): str(v) for k, v in payload.items() if v}
            except Exception as exc:  # noqa: BLE001 — normalization is best-effort
                logger.warning("caption normalization failed (attempt %d): %s", attempt + 1, exc)
        return {}  # best-effort: fall back to original tokens

    def _complete(self, user: str) -> str:
        if self._openai_compatible:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {"role": "user", "content": user},
                ],
                temperature=self._temperature,
                response_format={"type": "json_object"},
            )
            return resp.choices[0].message.content or ""
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            temperature=self._temperature,
            system=_SYSTEM,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")
