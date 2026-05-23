"""A CaptionNormalizer that builds its provider client only when normalization actually runs."""

from __future__ import annotations

from collections.abc import Callable

from reels.application.ports.caption_normalizer import CaptionNormalizer


class LazyCaptionNormalizer(CaptionNormalizer):
    def __init__(self, factory: Callable[[], CaptionNormalizer]) -> None:
        self._factory = factory
        self._delegate: CaptionNormalizer | None = None

    def normalize(self, tokens: list[str]) -> dict[str, str]:
        if not tokens:
            return {}
        if self._delegate is None:
            self._delegate = self._factory()
        return self._delegate.normalize(tokens)
