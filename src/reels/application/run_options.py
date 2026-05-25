"""Per-run options threaded into stage handlers (e.g. limiting which reels a stage processes)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reels.application.manifest import Manifest
from reels.application.pipeline_stage import Stage
from reels.domain.reel.reel import Reel


@dataclass(frozen=True, slots=True)
class RunOptions:
    """Options for a single pipeline run. Non-reel stages ignore these."""

    reel_indices: frozenset[int] | None = None  # if set, per-reel stages process only these indices


def selected_reels(manifest: Manifest, options: RunOptions | None) -> list[Reel]:
    """The reels a per-reel stage should process, honoring an optional --reel filter."""
    if options is not None and options.reel_indices is not None:
        return [r for r in manifest.reels if r.index in options.reel_indices]
    return list(manifest.reels)


# The reel-scoped stages, in order, paired with "is this stage already done for this reel?".
# Mirrors the per-stage completion the API reports (see schemas.ReelOut.stages).
def resume_stage_for_reel(reel: Reel, output_dir: Path) -> Stage:
    """The first reel-scoped stage not yet complete for ``reel`` — where a per-reel run should
    resume so it doesn't redo finished stages (GH-19). Completion is read from the reel's recorded
    artifacts (and, for package, the output file's existence). If every stage is already done,
    returns ``PLAN_LAYOUT`` so "Process this reel" still does a full re-render on a finished reel.
    """
    done: list[tuple[Stage, bool]] = [
        (Stage.PLAN_LAYOUT, reel.layout is not None),
        (Stage.CUT, reel.cut_path is not None),
        (Stage.REFRAME, reel.reframed_path is not None),
        (Stage.CAPTION, reel.captioned_path is not None),
        (Stage.BRAND, reel.final_path is not None),
        (Stage.PACKAGE, (output_dir / reel.output_filename()).exists()),
    ]
    for stage, complete in done:
        if not complete:
            return stage
    return Stage.PLAN_LAYOUT
