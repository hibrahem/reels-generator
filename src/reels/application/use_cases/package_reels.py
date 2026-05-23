"""package use case (spec §5.9): copy finished reels to the output folder with stable names and
write the per-source metadata sidecars.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.application.ports.manifest_repository import ManifestRepository
from reels.application.ports.sidecar_writer import SidecarEntry, SidecarWriter
from reels.application.run_options import RunOptions, selected_reels


class CannotPackage(Exception):
    """Raised when a reel cannot be packaged (it has not been branded/finalized)."""


@dataclass(slots=True)
class PackageReels:
    sidecars: SidecarWriter
    manifests: ManifestRepository
    output_dir: Path

    def execute(self, manifest: Manifest, options: RunOptions | None = None) -> Manifest:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        entries: list[SidecarEntry] = []
        for reel in selected_reels(manifest, options):
            if reel.final_path is None:
                raise CannotPackage(f"reel {reel.index} is not finalized — run brand first")
            dest = self.output_dir / reel.output_filename()
            shutil.copyfile(reel.final_path, dest)
            entries.append(
                SidecarEntry(
                    filename=reel.output_filename(),
                    start=reel.candidate.time_range.start,
                    end=reel.candidate.time_range.end,
                    title=reel.candidate.title,
                    hook=reel.candidate.hook,
                    caption=reel.candidate.caption,
                    mode=reel.mode.value if reel.mode else "",
                    confidence=float(reel.candidate.confidence),
                )
            )

        self.sidecars.write(manifest.source.id.value, entries, self.output_dir)
        manifest.mark_completed(Stage.PACKAGE)
        self.manifests.save(manifest)
        return manifest
