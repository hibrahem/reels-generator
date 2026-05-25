import { fmtClock, type TranscriptSegment } from "../lib/api";

export function TranscriptView({
  segments,
  currentTime,
  onSeek,
  selStart,
  selEnd,
  onSetStart,
  onSetEnd,
}: {
  segments: TranscriptSegment[];
  currentTime: number;
  onSeek: (t: number) => void;
  /** When provided, the view enters selection mode: each row gets set-start / set-end actions. */
  selStart?: number;
  selEnd?: number;
  onSetStart?: (t: number) => void;
  onSetEnd?: (t: number) => void;
}) {
  const selecting = onSetStart != null && onSetEnd != null;

  return (
    <div className="max-h-[420px] overflow-y-auto rounded-xl border border-border">
      {segments.map((seg, i) => {
        const playing = currentTime >= seg.start && currentTime < seg.end;
        // A segment is inside the selected cut when it overlaps [selStart, selEnd].
        const inRange =
          selecting && selStart != null && selEnd != null && seg.end > selStart && seg.start < selEnd;
        return (
          <div
            key={i}
            dir="rtl"
            className={`flex w-full items-start gap-3 border-b border-border/70 px-3 py-2 text-right transition last:border-0 ${
              inRange ? "bg-primary/15" : playing ? "bg-primary/10" : "hover:bg-muted/40"
            }`}
          >
            <button
              type="button"
              onClick={() => onSeek(seg.start)}
              dir="ltr"
              title="Seek here"
              className={`mt-0.5 shrink-0 font-mono text-[11px] ${
                playing ? "text-primary" : "text-muted-foreground"
              } hover:text-foreground`}
            >
              {fmtClock(seg.start)}
            </button>
            <button
              type="button"
              onClick={() => onSeek(seg.start)}
              className={`flex-1 text-right text-sm ${
                playing || inRange ? "text-foreground" : "text-muted-foreground"
              } hover:text-foreground`}
            >
              {seg.text.trim()}
            </button>
            {selecting && (
              <div dir="ltr" className="flex shrink-0 gap-1">
                <button
                  type="button"
                  onClick={() => onSetStart!(seg.start)}
                  title="Set reel start to this segment"
                  className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-primary/20 hover:text-primary"
                >
                  start
                </button>
                <button
                  type="button"
                  onClick={() => onSetEnd!(seg.end)}
                  title="Set reel end to this segment"
                  className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground hover:bg-primary/20 hover:text-primary"
                >
                  end
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
