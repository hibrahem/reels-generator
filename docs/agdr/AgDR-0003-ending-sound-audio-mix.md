# Ending-sound audio mix in the brand stage

> In the context of adding a branded "ending sound" that overlaps the last words of each reel and finishes as the outro begins, facing the fact that the brand stage concatenates intro/main/outro audio linearly, I decided to mix the sound into the main segment's tail as a pre-step using a duration-probed `adelay` + `amix`, to achieve precise end-alignment without disturbing the existing concat, accepting one extra audio-only encode of the main clip and an ffprobe call per reel.

## Context

The brand stage (`brand_reels.py` → `FFmpegVideoEditor.brand`) builds the final reel by concatenating `intro + main + outro` (video and audio) and overlaying the logo on the main segment. Audio is a linear concat of each segment's audio.

The ending sound must:
- play over the **tail of the main reel audio** (overlapping the last spoken words), not after it;
- **finish exactly at the outro boundary** (i.e. at the end of the main segment);
- mix on top of the original speech at a fixed reduced volume with **no ducking**;
- be a single global asset (`paths.ending_sound`), exactly like the outro;
- work whether or not an intro/outro/logo is configured.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Pre-mix the main clip's tail, then run existing brand logic** | Orthogonal to intro/outro/logo — all combinations work unchanged; small, isolated filtergraph; easy to test the delay math | One extra encode of the main clip (audio-only, video stream-copied) + one ffprobe call per reel |
| Inject the mix into the concat `filter_complex` directly | No extra pass | Couples ending-sound logic into the concat graph; must special-case the no-outro/logo-only/copy paths; harder to reason about and test |
| `areverse` → mix at head → `areverse` back (avoid probing) | No ffprobe needed | Double full-stream reverse; obscure; brittle to reason about; still re-encodes |

For end-alignment the sound's start offset is `main_duration − sound_duration`, so we need the main clip's duration. Probing with ffprobe is the clearest, most testable way to get it.

## Decision

Chosen: **pre-mix the main clip's tail as a separate ffmpeg pass**, then feed the result into the unchanged brand concat/logo/copy paths.

- `_probe_duration()` (ffprobe, located next to the configured ffmpeg binary) gives main + sound durations.
- `delay_ms = max(0, round((main_dur − sound_dur) * 1000))` — clamped so a sound longer than the reel simply starts at 0 and is trimmed to the reel length.
- Filtergraph: speech `[0:a]` resampled; sound `[1:a]` resampled, `volume=0.7`, `adelay=delay|delay`; `amix=inputs=2:duration=first:normalize=0` (normalize=0 keeps the speech at full level instead of halving it). Video is stream-copied (`-c:v copy`) so the main clip isn't re-encoded for video.
- The mix filtergraph string is built by a pure module-level helper so the delay/clamp math is unit-testable without invoking ffmpeg.
- Fixed `ENDING_SOUND_VOLUME = 0.7`; no per-reel state and no volume config field (per product decision: fixed reduced volume, no ducking, global scope).

## Consequences

- All branding combinations keep working; ending sound is independent of intro/outro/logo.
- `ending_sound: null` → the pre-step is skipped entirely, so existing output is unchanged.
- Cost: one ffprobe + one audio-only encode of the main clip per reel when an ending sound is set. Video is stream-copied, so no video quality loss.
- A volume change or ducking would be a follow-up (config field + sidechain), out of scope here.

## Artifacts

- Ticket: hibrahem/reels-generator#17
- Code: `src/reels/infrastructure/ffmpeg/ffmpeg_video_editor.py`, `src/reels/application/use_cases/brand_reels.py`, `src/reels/application/ports/video_editor.py`, `src/reels/infrastructure/config/settings.py`, `config.yaml`, `src/reels/presentation/container.py`
