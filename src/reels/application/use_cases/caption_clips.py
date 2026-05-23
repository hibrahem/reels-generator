"""caption use case (spec §5.7): burn word-by-word Arabic captions into each reframed clip."""

from __future__ import annotations

import re
from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.caption_normalizer import CaptionNormalizer
from reels.application.ports.caption_renderer import CaptionRenderer, CaptionWord
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.application.run_options import RunOptions, selected_reels

# Sentence/clause punctuation is bidi-neutral and from unreliable Whisper output; it makes
# word-by-word Arabic captions look scrambled/"flipped". Social captions omit it.
_PUNCTUATION = re.compile(r"[.,!?;:،؟؛…\"'«»()\[\]{}\-–—]+")


class CannotCaption(Exception):
    """Raised when a reel cannot be captioned (missing transcript or reframed clip)."""


@dataclass(slots=True)
class CaptionClips:
    transcripts: TranscriptRepository
    renderer: CaptionRenderer
    manifests: ManifestRepository
    strip_punctuation: bool = True
    normalizer: CaptionNormalizer | None = None
    normalize_english: bool = False

    def execute(self, manifest: Manifest, options: RunOptions | None = None) -> Manifest:
        if manifest.transcript_path is None:
            raise CannotCaption(f"'{manifest.source.id}' has no transcript")
        transcript = self.transcripts.load(manifest.transcript_path)

        reels = selected_reels(manifest, options)
        for reel in reels:
            if reel.reframed_path is None:
                raise CannotCaption(f"reel {reel.index} has not been reframed — run reframe first")

        words_by_reel = {
            reel.index: self._clip_words(
                transcript, reel.candidate.time_range.start, reel.candidate.time_range.end
            )
            for reel in reels
        }
        mapping = self._english_mapping(words_by_reel)

        captioned_dir = manifest.source.working_dir / "captioned"
        for reel in reels:
            words = [self._apply_mapping(w, mapping) for w in words_by_reel[reel.index]]
            out_path = captioned_dir / f"reel_{reel.index:02d}.mp4"
            self.renderer.burn_in(reel.reframed_path, words, out_path)
            reel.record_captioned(out_path)

        manifest.mark_completed(Stage.CAPTION)
        self.manifests.save(manifest)
        return manifest

    def _english_mapping(self, words_by_reel: dict[int, list[CaptionWord]]) -> dict[str, str]:
        if not (self.normalize_english and self.normalizer):
            return {}
        tokens = sorted({w.text for words in words_by_reel.values() for w in words})
        return self.normalizer.normalize(tokens)

    @staticmethod
    def _apply_mapping(word: CaptionWord, mapping: dict[str, str]) -> CaptionWord:
        replacement = mapping.get(word.text)
        if replacement is None:
            return word
        return CaptionWord(text=replacement, start=word.start, end=word.end)

    def _clip_words(self, transcript, start: float, end: float) -> list[CaptionWord]:
        words = []
        for w in transcript.words_within(start, end):
            text = w.text.strip()
            if self.strip_punctuation:
                text = _PUNCTUATION.sub("", text).strip()
            if not text:  # word was pure punctuation — drop it
                continue
            words.append(
                CaptionWord(
                    text=text,
                    start=max(w.start - start, 0.0),
                    end=max(w.end - start, 0.0),
                )
            )
        return words
