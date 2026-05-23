"""reframe use case (spec §5.6): apply each reel's layout geometry to its cut, producing 9:16."""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.video_editor import VideoEditor
from reels.application.run_options import RunOptions, selected_reels


class CannotReframe(Exception):
    """Raised when a reel is missing the inputs reframe needs (layout or cut)."""


@dataclass(slots=True)
class ReframeClips:
    editor: VideoEditor
    manifests: ManifestRepository

    def execute(self, manifest: Manifest, options: RunOptions | None = None) -> Manifest:
        reframed_dir = manifest.source.working_dir / "reframed"
        for reel in selected_reels(manifest, options):
            if reel.layout is None:
                raise CannotReframe(f"reel {reel.index} has no layout — run plan-layout first")
            if reel.cut_path is None:
                raise CannotReframe(f"reel {reel.index} has not been cut — run cut first")
            out_path = reframed_dir / f"reel_{reel.index:02d}.mp4"
            self.editor.reframe(reel.cut_path, reel.layout, out_path)
            reel.record_reframe(out_path)

        manifest.mark_completed(Stage.REFRAME)
        self.manifests.save(manifest)
        return manifest
