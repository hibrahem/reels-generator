r"""Build an ASS subtitle document with word-by-word ("karaoke") highlighting (spec §5.7).

Each caption line is a short chunk of words rendered as ONE Dialogue event using native ASS
karaoke (``{\k}``) tags — one per word, timed to the speech. libass shapes (joins Arabic letters),
applies the bidi algorithm to the whole line, and sweeps the highlight word by word. Words start in
the base colour (SecondaryColour) and turn the active colour (PrimaryColour) as they're spoken.

Text is raw logical-order Arabic/Latin: our ffmpeg's libass has HarfBuzz + FriBidi, so it does the
shaping and reordering. Pre-shaping, or per-word ``{\c}`` colour spans, would fragment the line and
break libass's bidi — so we rely on ``{\k}``, which keeps the line a single bidi run.
"""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.ports.caption_renderer import CaptionWord

# Start a new caption line after this many words or this long a pause.
_MAX_GAP_SECONDS = 0.8


@dataclass(frozen=True, slots=True)
class CaptionStyle:
    font_family: str
    base_font_size: int
    active_font_size: int
    base_color: str  # &HAABBGGRR
    active_color: str  # &HAABBGGRR
    position: str  # "bottom" | "center"
    safe_margin_v: int
    safe_margin_h: int
    max_words_per_line: int
    outline: int
    shadow: int
    play_res_x: int
    play_res_y: int
    bold: bool = True
    box: bool = True
    box_color: str = "&H90000000"
    reverse_word_order: bool = False  # flip per-line word order (first-spoken word on the left)


def build_ass(words: list[CaptionWord], style: CaptionStyle) -> str:
    lines = [_header(style), _styles(style), _events_header()]

    for chunk in _chunk_words(words, style.max_words_per_line):
        start = chunk[0].start
        end = max(chunk[-1].end, start + 0.1)
        parts = []
        for i, word in enumerate(chunk):
            nxt = chunk[i + 1].start if i + 1 < len(chunk) else word.end
            dur_cs = max(1, round((nxt - word.start) * 100))  # karaoke unit = centiseconds
            parts.append(f"{{\\k{dur_cs}}}{word.text}")
        if style.reverse_word_order:
            # Emit reversed: after libass's RTL bidi this puts the first-spoken word on the left.
            parts.reverse()
        text = " ".join(parts)
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def _chunk_words(words: list[CaptionWord], max_per_line: int) -> list[list[CaptionWord]]:
    chunks: list[list[CaptionWord]] = []
    current: list[CaptionWord] = []
    for word in words:
        if current and (
            len(current) >= max_per_line or word.start - current[-1].end > _MAX_GAP_SECONDS
        ):
            chunks.append(current)
            current = []
        current.append(word)
    if current:
        chunks.append(current)
    return chunks


def _header(style: CaptionStyle) -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {style.play_res_x}\n"
        f"PlayResY: {style.play_res_y}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
    )


def _styles(style: CaptionStyle) -> str:
    alignment = 2 if style.position == "bottom" else 5  # 2 = bottom-center, 5 = middle-center
    fmt = (
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    # PrimaryColour = sung (active) colour, SecondaryColour = unsung (base) colour: as each word's
    # karaoke time arrives it flips from base to active.
    bold = 1 if style.bold else 0
    if style.box:
        # BorderStyle 3 = opaque box; OutlineColour is the box fill, Outline its padding.
        border_style, outline_colour, outline, shadow = 3, style.box_color, max(style.outline, 6), 0
    else:
        border_style, outline_colour, outline, shadow = 1, "&H00101010", style.outline, style.shadow
    style_line = (
        f"Style: Default,{style.font_family},{style.base_font_size},{style.active_color},"
        f"{style.base_color},{outline_colour},&H00000000,{bold},0,0,0,100,100,0,0,"
        f"{border_style},{outline},{shadow},{alignment},{style.safe_margin_h},"
        f"{style.safe_margin_h},{style.safe_margin_v},1"
    )
    return f"\n[V4+ Styles]\n{fmt}\n{style_line}\n"


def _events_header() -> str:
    return (
        "\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"
    )


def _ts(seconds: float) -> str:
    seconds = max(seconds, 0.0)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    centis = round((secs - int(secs)) * 100)
    return f"{int(hours)}:{int(minutes):02d}:{int(secs):02d}.{centis:02d}"
