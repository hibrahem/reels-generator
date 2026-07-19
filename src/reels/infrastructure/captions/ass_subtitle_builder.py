r"""Build an ASS subtitle document with word-by-word highlighting (spec §5.7).

Each caption line is a short chunk of words rendered as ONE Dialogue event. The spoken word
"lights up" (colour flip, optional size pop) at its own moment and stays lit, so an Arabic
line sweeps right-to-left, an English line left-to-right, and a code-switched line follows
natural bidi reading order.

Why NOT native ``{\k}`` karaoke: empirically (see tests/caption_harness) our vendored
libass (a) lays every line out with an immovable LTR base paragraph direction — Unicode
direction marks are ignored — and (b) applies both karaoke timing and per-word override
blocks to VISUAL word slots left-to-right, regardless of which word each block precedes in
the text. ``{\k}`` fill is cumulative in that visual order, so it can only ever sweep
left-to-right; it also pairs each word with the duration of whatever word occupies its
visual slot, drifting out of sync when word durations differ.

Instead the builder coordinates two permutations from ``text_direction.plan_line``:

  - words are EMITTED in an order chosen so libass's own bidi displays the layout the
    resolved direction calls for (logical order for RTL lines; RTL runs pre-reversed
    where needed);
  - override block j (= visual slot j) carries the TIMING of the word displayed in that
    slot: an anchored colour flip ``\1c<base>\t(start,+50ms,\1c<active>)`` plus the size
    "pop" (``\fs`` anchor + two ``\t`` ramps).

Anchors matter: override tags persist to the end of the line, so every block re-anchors
colour (and size) before animating. The blue LSB of both colours alternates per block —
imperceptible, but it keeps adjacent words' style runs permanently distinct so libass never
re-merges runs mid-line (merging visibly shifts glyph positions as colours flip).

Text stays raw logical-order Arabic/Latin: libass (HarfBuzz + FriBidi) does the shaping.
"""

from __future__ import annotations

from dataclasses import dataclass

from reels.application.ports.caption_renderer import CaptionWord
from reels.infrastructure.captions.text_direction import line_direction, plan_line

# Start a new caption line after this many words or this long a pause.
_MAX_GAP_SECONDS = 0.8

# The colour flip is near-instant, like a karaoke syllable flip.
_COLOR_FLIP_MS = 50


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
    direction: str = "auto"  # "auto" (per-line detection) | "rtl" | "ltr"


def build_ass(words: list[CaptionWord], style: CaptionStyle) -> str:
    lines = [_header(style), _styles(style), _events_header()]

    for chunk in _chunk_words(words, style.max_words_per_line):
        start = chunk[0].start
        end = max(chunk[-1].end, start + 0.1)
        # word i is "active" from its start until the next word starts (last: its own end)
        windows_ms = []
        for i, word in enumerate(chunk):
            nxt = chunk[i + 1].start if i + 1 < len(chunk) else word.end
            s = max(0, round((word.start - start) * 1000))
            e = max(s + 1, round((nxt - start) * 1000))
            windows_ms.append((s, e))

        texts = [w.text for w in chunk]
        direction = style.direction if style.direction != "auto" else line_direction(texts)
        visual, emission = plan_line(texts, direction)

        parts = []
        for j in range(len(chunk)):
            window = windows_ms[visual[j]]  # block j styles visual slot j
            parts.append(f"{{{_block_override(style, window, j)}}}{texts[emission[j]]}")
        text = " ".join(parts)
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def _block_override(style: CaptionStyle, window: tuple[int, int], block_index: int) -> str:
    start_ms, end_ms = window
    base = _inline_color(style.base_color, block_index)
    active = _inline_color(style.active_color, block_index)
    flip_end = max(start_ms + 1, min(start_ms + _COLOR_FLIP_MS, end_ms))
    override = f"\\1c{base}\\t({start_ms},{flip_end},\\1c{active})"
    if style.active_font_size != style.base_font_size:
        override += _grow_transform(style, start_ms, end_ms)
    return override


def _inline_color(ass_color: str, block_index: int) -> str:
    r"""``&HAABBGGRR`` style colour -> ``&HBBGGRR&`` for ``\1c``, blue LSB set per block.

    Alternating the blue LSB keeps adjacent words' styles permanently distinct — see the
    module docstring (prevents run-merge layout jitter).
    """
    digits = ass_color.strip("&H").lstrip("hH")[-8:].upper().zfill(8)
    blue = (int(digits[2:4], 16) & ~1) | (block_index % 2)
    return f"&H{blue:02X}{digits[4:8]}&"


# Fraction of the word's spoken window spent ramping the size up (and, separately, back
# down). Keeps the pop readable as a karaoke "bounce" rather than an instant jump.
_GROW_RAMP = 0.25


def _grow_transform(style: CaptionStyle, start_ms: int, end_ms: int) -> str:
    r"""Animate this block's font size: base -> active during its window, then back.

    Emits ``\fs<base>`` to anchor the resting size, then two ``\t(t1,t2,\fs<size>)``
    transforms (times are milliseconds from the LINE start).
    """
    base, active = style.base_font_size, style.active_font_size
    span = end_ms - start_ms
    ramp = max(1, round(span * _GROW_RAMP))
    up_end = start_ms + ramp
    down_start = max(up_end, end_ms - ramp)
    return (
        f"\\fs{base}"
        f"\\t({start_ms},{up_end},\\fs{active})"
        f"\\t({down_start},{end_ms},\\fs{base})"
    )


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
    # Every word carries an explicit \1c anchor, so PrimaryColour only shows on untagged
    # text (there is none); keep base colour there for safety. SecondaryColour is unused.
    bold = 1 if style.bold else 0
    if style.box:
        # BorderStyle 3 = opaque box; OutlineColour is the box fill, Outline its padding.
        border_style, outline_colour, outline, shadow = 3, style.box_color, max(style.outline, 6), 0
    else:
        border_style, outline_colour, outline, shadow = 1, "&H00101010", style.outline, style.shadow
    style_line = (
        f"Style: Default,{style.font_family},{style.base_font_size},{style.base_color},"
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
