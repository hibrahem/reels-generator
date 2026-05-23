"""Writes the per-source reels.json and human-readable reels.md sidecars (spec §5.9)."""

from __future__ import annotations

import json
from pathlib import Path

from reels.application.ports.sidecar_writer import SidecarEntry, SidecarWriter


def _clock(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes:02d}:{secs:02d}"


class FileSidecarWriter(SidecarWriter):
    def write(
        self, source_id: str, entries: list[SidecarEntry], output_dir: Path
    ) -> tuple[Path, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / f"{source_id}.reels.json"
        md_path = output_dir / f"{source_id}.reels.md"

        json_path.write_text(
            json.dumps(
                {
                    "source": source_id,
                    "reels": [
                        {
                            "filename": e.filename,
                            "start": e.start,
                            "end": e.end,
                            "title": e.title,
                            "hook": e.hook,
                            "caption": e.caption,
                            "mode": e.mode,
                            "confidence": e.confidence,
                        }
                        for e in entries
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        lines = [f"# Reels — {source_id}", "", f"{len(entries)} reel(s).", ""]
        for i, e in enumerate(entries, start=1):
            lines += [
                f"## {i:02d}. {e.title}",
                "",
                f"- **File:** `{e.filename}`",
                f"- **Source span:** {_clock(e.start)}–{_clock(e.end)} "
                f"({e.end - e.start:.0f}s)",
                f"- **Mode:** {e.mode}  ·  **Confidence:** {e.confidence:.2f}",
                f"- **Hook:** {e.hook}",
                f"- **Caption:** {e.caption}",
                "",
            ]
        md_path.write_text("\n".join(lines), encoding="utf-8")
        return json_path, md_path
