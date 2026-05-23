"""Prompt construction for the clip-selection stage (spec §5.3).

The LLM sees transcript text only — never pixels, never crop geometry. The content is typically
Egyptian colloquial Arabic with inline English technical terms, so the prompt asks for hooks and
captions in that same register and keeps English terms as-is.
"""

from __future__ import annotations

from reels.domain.reel.clip_selector import SelectionConstraints
from reels.domain.transcript.transcript import Transcript

SELECTION_SYSTEM = """You are a senior short-form video editor for an educational channel.
You receive the timestamped transcript of a long-form Arabic course lecture (Egyptian colloquial
Arabic, with English technical terms mixed in) and pick the self-contained teaching moments that
would work as standalone vertical reels.

Rules:
- Pick ONLY moments that make complete sense without surrounding context. A viewer who lands on the
  clip cold should still get a full, satisfying idea.
- The number of clips is content-driven. Return as many genuinely strong moments as exist — and
  return an empty list if the source has none. Do not pad.
- Clips MUST NOT overlap in time.
- DURATION IS A HARD CONSTRAINT: every clip's (end - start) MUST be within the min/max window given
  in the user message. Clips outside the window are discarded, so do not return them. If a strong
  moment runs longer than the max, pick the single best self-contained sub-window that fits — do NOT
  return whole topics or multi-minute spans.
- start/end are in SECONDS (floats), measured from the beginning of the video, and must lie within
  the video duration. Align them to natural sentence boundaries from the transcript.
- Write `hook` and `caption` in the SAME register as the source: Egyptian colloquial Arabic, keeping
  English technical terms (e.g. Coupling, API Gateway) in Latin script exactly as spoken.
- `title` is a short internal label (English or Arabic, your choice).
- `reason` explains, in English, why this stands alone and why it will land.
- `confidence` is your 0..1 judgment of how strong the clip is.
- `visual_dependent` is true if understanding the moment leans on slides/diagrams rather than just
  the talk. This is a hint for a later layout stage; it does not affect your time selection.

Respond with a single JSON object of the form:
{"clips": [{"start": 12.0, "end": 48.5, "title": "...", "hook": "...", "caption": "...",
"reason": "...", "confidence": 0.82, "visual_dependent": false}]}
Return ONLY the JSON object, no prose, no markdown fences."""


def build_user_prompt(transcript: Transcript, constraints: SelectionConstraints) -> str:
    lines = [
        f"Video duration: {transcript.duration_seconds:.1f} seconds.",
        f"HARD clip duration window: every clip must be between "
        f"{constraints.min_clip_seconds:.0f} and {constraints.max_clip_seconds:.0f} seconds long. "
        f"Reject your own picks that fall outside this range before answering.",
        "",
        "Transcript (each line: [start-end] text):",
    ]
    for seg in transcript.segments:
        text = " ".join(seg.text.split())  # collapse whitespace
        lines.append(f"[{seg.start:.1f}-{seg.end:.1f}] {text}")
    return "\n".join(lines)
