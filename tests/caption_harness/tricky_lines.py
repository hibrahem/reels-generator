"""Hand-picked tricky caption lines for the Arabic rendering gate (spec §5.7, §10 slice 4).

These are the lines the dedicated caption harness must render correctly before captions are wired
into the batch path. Used now as fixtures; the renderer that consumes them arrives in slice 4.

Each line targets a specific failure mode of naive Arabic burn-in.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrickyLine:
    label: str
    text: str
    note: str


TRICKY_LINES: tuple[TrickyLine, ...] = (
    TrickyLine(
        label="pure_arabic",
        text="مرحبا بكم في الدرس الأول من هذه الدورة",
        note="connected letters must stay joined; reading order right-to-left",
    ),
    TrickyLine(
        label="arabic_with_numbers",
        text="افتح الصفحة رقم 42 وابدأ التمرين",
        note="bidi: Arabic + Western digits in one line",
    ),
    TrickyLine(
        label="code_switch",
        text="سنستخدم مكتبة Python اسمها FastAPI لبناء الخادم",
        note="bidi: embedded Latin words must render in correct visual order",
    ),
    TrickyLine(
        label="tatweel_and_diacritics",
        text="هَذَا مِثَالٌ بِالتَّشْكِيلِ الكَامِلِ",
        note="diacritics must attach to the correct base glyphs",
    ),
    TrickyLine(
        label="fast_speech_short_words",
        text="و ثم بعد ذلك مباشرة ننتقل",
        note="very short word durations stress per-word karaoke timing",
    ),
)
