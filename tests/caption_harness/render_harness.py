"""Render the tricky Arabic/English caption lines to frames for visual verification (spec §5.7).

This is the caption gate: run it, then eyeball the PNGs for correct Arabic shaping (connected
letters), right-to-left order, and code-switched English in the right visual position.

    uv run python tests/caption_harness/render_harness.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from reels.application.ports.caption_renderer import CaptionWord
from reels.infrastructure.captions.ass_subtitle_builder import CaptionStyle, build_ass
from reels.infrastructure.config.settings import load_settings

sys.path.insert(0, str(Path(__file__).parent))
from tricky_lines import TRICKY_LINES  # noqa: E402

_WORD_SECONDS = 0.6


def _words(text: str) -> list[CaptionWord]:
    return [
        CaptionWord(w, i * _WORD_SECONDS, (i + 1) * _WORD_SECONDS)
        for i, w in enumerate(text.split())
    ]


def _style(settings) -> CaptionStyle:
    c = settings.captions
    return CaptionStyle(
        font_family=c.font_family,
        base_font_size=c.base_font_size,
        active_font_size=c.active_font_size,
        base_color=c.base_color,
        active_color=c.active_color,
        position="center",  # center on the harness background for easy viewing
        safe_margin_v=c.safe_margin_v,
        safe_margin_h=c.safe_margin_h,
        max_words_per_line=c.max_words_per_line,
        outline=c.outline,
        shadow=c.shadow,
        play_res_x=settings.output.width,
        play_res_y=settings.output.height,
        bold=c.bold,
        box=c.box,
        box_color=c.box_color,
    )


def main() -> None:
    settings = load_settings(Path("config.yaml"))
    ffmpeg = str(settings.paths.ffmpeg) if settings.paths.ffmpeg else "ffmpeg"
    fonts_dir = settings.paths.font.parent
    style = _style(settings)

    out_dir = Path("work/caption_harness")
    out_dir.mkdir(parents=True, exist_ok=True)

    for line in TRICKY_LINES:
        words = _words(line.text)
        ass_path = out_dir / f"{line.label}.ass"
        ass_path.write_text(build_ass(words, style), encoding="utf-8")
        mid = max(0.3, len(words) * _WORD_SECONDS / 2)
        png = out_dir / f"{line.label}.png"
        vf = f"subtitles={ass_path}:fontsdir={fonts_dir}"
        subprocess.run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "color=c=0x1b2330:s=1080x1920:d=3",
                "-vf", vf, "-ss", f"{mid:.2f}", "-frames:v", "1", str(png),
            ],
            check=True,
        )
        print(f"rendered {line.label:28s} -> {png}  ({line.note})")


if __name__ == "__main__":
    main()
