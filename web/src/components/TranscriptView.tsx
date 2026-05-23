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
    <div className="max-h-[420px] overflow-y-auto rounded-xl border border-zinc-800">
      {segments.map((seg, i) => {
        const active = currentTime >= seg.start && currentTime < seg.end;
        return (
          <button
            key={i}
            onClick={() => onSeek(seg.start)}
            dir="rtl"
            className={`flex w-full items-start gap-3 border-b border-zinc-800/70 px-3 py-2 text-right transition last:border-0 hover:bg-zinc-800/40 ${
              active ? "bg-indigo-500/10" : ""
            }`}
          >
            <span
              dir="ltr"
              className={`mt-0.5 shrink-0 font-mono text-[11px] ${
                active ? "text-indigo-300" : "text-zinc-500"
              }`}
            >
              {fmtClock(seg.start)}
            </span>
            <span className={`text-sm ${active ? "text-zinc-100" : "text-zinc-300"}`}>
              {seg.text.trim()}
            </span>
          </button>
        );
      })}
    </div>
  );
}
