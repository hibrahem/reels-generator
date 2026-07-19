"""Word-level bidi planning for caption lines.

Our vendored libass has an immovable LTR base paragraph direction (direction marks like
U+200F are ignored) and applies per-word override blocks to VISUAL word slots left-to-right,
regardless of which word each block precedes in the text. Getting a right-to-left caption
that highlights the spoken word therefore takes two coordinated permutations:

  - ``visual_order`` V: V[j] is the logical (spoken) index of the word displayed at visual
    slot j, left-to-right — word-level UAX#9 for the requested paragraph direction. The
    direction orders the RUNS; each script run always reads its own way (an Arabic run is
    right-to-left even in an ``ltr`` paragraph).
  - ``emission_order`` E: the order to emit words in the dialogue text so that libass's own
    LTR-base bidi (which reverses each maximal run of RTL words) displays exactly V.

The builder emits word E[j] at text position j and gives that override block the timing of
word V[j], so every visual slot lights up when its word is spoken.
"""

from __future__ import annotations

import unicodedata

Direction = str  # "rtl" | "ltr"

_RTL_BIDI_CLASSES = {"R", "AL"}
_LTR_BIDI_CLASSES = {"L"}


def word_direction(word: str) -> Direction | None:
    """Direction of a word's first strong character, or None if it has none."""
    for char in word:
        bidi = unicodedata.bidirectional(char)
        if bidi in _RTL_BIDI_CLASSES:
            return "rtl"
        if bidi in _LTR_BIDI_CLASSES:
            return "ltr"
    return None


def line_direction(words: list[str]) -> Direction:
    """Paragraph direction of a caption line: its first strong word, else rtl.

    The rtl fallback suits this product — an all-neutral line (numbers, symbols) inside
    Arabic content should behave like its surroundings.
    """
    for word in words:
        direction = word_direction(word)
        if direction is not None:
            return direction
    return "rtl"


def plan_line(words: list[str], direction: Direction) -> tuple[list[int], list[int]]:
    """Return (visual_order, emission_order) for a caption line.

    visual_order[j] = logical index shown at visual slot j (left-to-right).
    emission_order[j] = logical index to emit at text position j so libass displays
    visual_order.
    """
    dirs = _resolved_word_directions(words, direction)
    # Word-level UAX#9: the paragraph direction orders the runs (rtl reverses run order),
    # while each run always reads its own way — RTL runs right-to-left (mirrored), LTR
    # runs left-to-right.
    runs = _runs(dirs)
    if direction == "rtl":
        runs = list(reversed(runs))
    visual: list[int] = []
    for run_dir, indices in runs:
        visual.extend(reversed(indices) if run_dir == "rtl" else indices)
    # libass will reverse each maximal RTL segment of the emitted text; pre-reverse
    # those segments so the displayed order comes out as `visual`.
    emission: list[int] = []
    for run_dir, slots in _runs([dirs[i] for i in visual]):
        segment = [visual[j] for j in slots]
        emission.extend(reversed(segment) if run_dir == "rtl" else segment)
    return visual, emission


def _resolved_word_directions(words: list[str], line_dir: Direction) -> list[Direction]:
    """Per-word direction with neutral words attached to the preceding run (UAX#9-ish)."""
    resolved: list[Direction | None] = [word_direction(w) for w in words]
    previous: Direction | None = None
    for i, direction in enumerate(resolved):
        if direction is None:
            resolved[i] = previous
        else:
            previous = direction
    # leading neutrals attach to the following run, else the line direction
    following: Direction | None = None
    for i in range(len(resolved) - 1, -1, -1):
        if resolved[i] is None:
            resolved[i] = following if following is not None else line_dir
        else:
            following = resolved[i]
    return resolved  # type: ignore[return-value]


def _runs(dirs: list[Direction]) -> list[tuple[Direction, list[int]]]:
    """Group positions 0..n-1 into maximal same-direction runs, in order."""
    runs: list[tuple[Direction, list[int]]] = []
    for i, direction in enumerate(dirs):
        if runs and runs[-1][0] == direction:
            runs[-1][1].append(i)
        else:
            runs.append((direction, [i]))
    return runs
