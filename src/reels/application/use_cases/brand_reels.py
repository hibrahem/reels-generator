"""brand use case (spec §5.8): prepend intro, append outro, overlay logo per reel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.video_editor import LogoOverlay, VideoEditor
from reels.application.run_options import RunOptions, selected_reels


class CannotBrand(Exception):
    """Raised when a reel cannot be branded (it has not been captioned)."""


@dataclass(slots=True)
class BrandReels:
    editor: VideoEditor
    manifests: ManifestRepository
    intro: Path | None = None
    outro: Path | None = None
    logo: LogoOverlay | None = None
    ending_sound: Path | None = None

    def execute(self, manifest: Manifest, options: RunOptions | None = None) -> Manifest:
        final_dir = manifest.source.working_dir / "final"
        for reel in selected_reels(manifest, options):
            if reel.captioned_path is None:
                raise CannotBrand(f"reel {reel.index} has not been captioned — run caption first")
            out_path = final_dir / f"reel_{reel.index:02d}.mp4"
            self.editor.brand(
                reel.captioned_path,
                out_path,
                intro=self.intro,
                outro=self.outro,
                logo=self.logo,
                ending_sound=self.ending_sound,
            )
            reel.finalize(out_path)

        manifest.mark_completed(Stage.BRAND)
        self.manifests.save(manifest)
        return manifest
