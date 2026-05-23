"""Port for normalizing transliterated English terms in caption words to Latin script (spec §5.7).

Egyptian-Arabic lecturers say English tech terms that Whisper transcribes into Arabic letters
(e.g. "الكوبلينج" → Coupling). This maps those tokens back to Latin for readable captions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class CaptionNormalizer(ABC):
    @abstractmethod
    def normalize(self, tokens: list[str]) -> dict[str, str]:
        """Map each transliterated-English token to its Latin spelling.

        Returns a dict keyed by the original token; Arabic-only tokens (and tokens already in
        Latin) are omitted. Token-keyed (not positional), so it never disturbs word alignment.
        """
        raise NotImplementedError
