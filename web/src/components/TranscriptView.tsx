import { fmtClock, type TranscriptSegment } from "../lib/api";

export function TranscriptView({
  segments,
  currentTime,
  onSeek,
}: {
  segments: TranscriptSegment[];
  currentTime: number;
  onSeek: (t: number) => void;
}) {
  return (
    <div className="max-h-[420px] overflow-y-auto rounded-xl border border-border">
      {segments.map((seg, i) => {
        const active = currentTime >= seg.start && currentTime < seg.end;
        return (
          <button
            key={i}
            onClick={() => onSeek(seg.start)}
            dir="rtl"
            className={`flex w-full items-start gap-3 border-b border-border/70 px-3 py-2 text-right transition last:border-0 hover:bg-muted/40 ${
              active ? "bg-primary/10" : ""
            }`}
          >
            <span
              dir="ltr"
              className={`mt-0.5 shrink-0 font-mono text-[11px] ${
                active ? "text-primary" : "text-muted-foreground"
              }`}
            >
              {fmtClock(seg.start)}
            </span>
            <span className={`text-sm ${active ? "text-foreground" : "text-muted-foreground"}`}>
              {seg.text.trim()}
            </span>
          </button>
        );
      })}
    </div>
  );
}
