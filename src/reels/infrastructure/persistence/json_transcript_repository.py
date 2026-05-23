"""JSON persistence of the raw word-level transcript (spec §5.2)."""

from __future__ import annotations

import json
from pathlib import Path

from reels.application.ports.transcript_repository import TranscriptRepository
from reels.domain.transcript.transcript import Segment, Transcript, Word

TRANSCRIPT_FILENAME = "transcript.json"


class JsonTranscriptRepository(TranscriptRepository):
    def save(self, transcript: Transcript, working_dir: Path) -> Path:
        working_dir.mkdir(parents=True, exist_ok=True)
        path = working_dir / TRANSCRIPT_FILENAME
        payload = {
            "source_id": transcript.source_id,
            "language": transcript.language,
            "duration_seconds": transcript.duration_seconds,
            "segments": [
                {
                    "text": seg.text,
                    "start": seg.start,
                    "end": seg.end,
                    "words": [
                        {
                            "text": w.text,
                            "start": w.start,
                            "end": w.end,
                            "probability": w.probability,
                        }
                        for w in seg.words
                    ],
                }
                for seg in transcript.segments
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, path: Path) -> Transcript:
        data = json.loads(path.read_text(encoding="utf-8"))
        segments = tuple(
            Segment(
                text=seg["text"],
                start=seg["start"],
                end=seg["end"],
                words=tuple(
                    Word(
                        text=w["text"],
                        start=w["start"],
                        end=w["end"],
                        probability=w.get("probability"),
                    )
                    for w in seg.get("words", [])
                ),
            )
            for seg in data.get("segments", [])
        )
        return Transcript(
            source_id=data["source_id"],
            language=data["language"],
            duration_seconds=data["duration_seconds"],
            segments=segments,
        )
