"""cut use case (spec §5.5): extract each selected clip from the source with an accurate cut."""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.video_editor import VideoEditor
from reels.application.run_options import RunOptions, selected_reels


@dataclass(slots=True)
class CutClips:
    editor: VideoEditor
    manifests: ManifestRepository

    def execute(self, manifest: Manifest, options: RunOptions | None = None) -> Manifest:
        cuts_dir = manifest.source.working_dir / "cuts"
        for reel in selected_reels(manifest, options):
            out_path = cuts_dir / f"reel_{reel.index:02d}.mp4"
            self.editor.cut(manifest.source.path, reel.candidate.time_range, out_path)
            reel.record_cut(out_path)

        manifest.mark_completed(Stage.CUT)
        self.manifests.save(manifest)
        return manifest
