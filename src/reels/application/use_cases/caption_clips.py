"""caption use case (spec §5.7): burn word-by-word Arabic captions into each reframed clip."""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.caption_renderer import CaptionRenderer, CaptionWord
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.transcript_repository import TranscriptRepository
from reels.application.run_options import RunOptions, selected_reels


class CannotCaption(Exception):
    """Raised when a reel cannot be captioned (missing transcript or reframed clip)."""


@dataclass(slots=True)
class CaptionClips:
    transcripts: TranscriptRepository
    renderer: CaptionRenderer
    manifests: ManifestRepository

    def execute(self, manifest: Manifest, options: RunOptions | None = None) -> Manifest:
        if manifest.transcript_path is None:
            raise CannotCaption(f"'{manifest.source.id}' has no transcript")
        transcript = self.transcripts.load(manifest.transcript_path)

        captioned_dir = manifest.source.working_dir / "captioned"
        for reel in selected_reels(manifest, options):
            if reel.reframed_path is None:
                raise CannotCaption(f"reel {reel.index} has not been reframed — run reframe first")
            words = self._clip_words(transcript, reel.candidate.time_range.start,
                                     reel.candidate.time_range.end)
            out_path = captioned_dir / f"reel_{reel.index:02d}.mp4"
            self.renderer.burn_in(reel.reframed_path, words, out_path)
            reel.record_captioned(out_path)

        manifest.mark_completed(Stage.CAPTION)
        self.manifests.save(manifest)
        return manifest

    @staticmethod
    def _clip_words(transcript, start: float, end: float) -> list[CaptionWord]:
        words = []
        for w in transcript.words_within(start, end):
            words.append(
                CaptionWord(
                    text=w.text.strip(),
                    start=max(w.start - start, 0.0),
                    end=max(w.end - start, 0.0),
                )
            )
        return words
