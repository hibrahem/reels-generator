import { useState } from "react";
import { fmtClock, reelMediaUrl, type Reel, type ReelStage } from "../lib/api";

const REEL_STAGES: ReelStage[] = ["plan-layout", "cut", "reframe", "caption", "brand", "package"];

function ConfidenceBadge({ value }: { value: number }) {
  const tone =
    value >= 0.85 ? "bg-emerald-500/20 text-emerald-300" : "bg-zinc-700/60 text-zinc-300";
  return <span className={`rounded px-1.5 py-0.5 text-xs ${tone}`}>{value.toFixed(2)}</span>;
}

export function ReelCard({
  videoId,
  reel,
  active,
  onPlaySpan,
}: {
  videoId: string;
  reel: Reel;
  active: boolean;
  onPlaySpan: () => void;
}) {
  const [showFinished, setShowFinished] = useState(false);
  const packaged = reel.stages.package;

  return (
    <div
      dir="rtl"
      className={`rounded-xl border bg-zinc-900/60 p-3 transition ${
        active ? "border-indigo-500" : "border-zinc-800"
      }`}
    >
      <div className="flex items-start justify-between gap-2" dir="ltr">
        <div className="flex items-center gap-2">
          <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">
            {reel.index.toString().padStart(2, "0")}
          </span>
          <span className="text-xs text-zinc-400">
            {fmtClock(reel.start)}–{fmtClock(reel.end)} · {reel.duration.toFixed(0)}s
          </span>
        </div>
        <div className="flex items-center gap-1">
          {reel.mode && (
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
              {reel.mode}
            </span>
          )}
          <ConfidenceBadge value={reel.confidence} />
        </div>
      </div>

      <h4 className="mt-2 font-medium text-zinc-100" dir="auto">
        {reel.title}
      </h4>
      {reel.hook && <p className="mt-1 text-sm text-zinc-300" dir="auto">{reel.hook}</p>}
      {reel.caption && (
        <p className="mt-1 line-clamp-2 text-xs text-zinc-500" dir="auto">
          {reel.caption}
        </p>
      )}

      <div className="mt-2 flex flex-wrap gap-1" dir="ltr">
        {REEL_STAGES.map((s) => (
          <span
            key={s}
            title={s}
            className={`rounded px-1.5 py-0.5 text-[10px] ${
              reel.stages[s] ? "bg-emerald-500/20 text-emerald-300" : "bg-zinc-800 text-zinc-500"
            }`}
          >
            {s}
          </span>
        ))}
      </div>

      <div className="mt-3 flex gap-2" dir="ltr">
        <button
          onClick={onPlaySpan}
          className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs text-zinc-200 transition hover:bg-zinc-700"
        >
          ▶ Play span
        </button>
        {packaged && (
          <button
            onClick={() => setShowFinished((v) => !v)}
            className="rounded-lg bg-indigo-600/80 px-2.5 py-1 text-xs text-white transition hover:bg-indigo-500"
          >
            {showFinished ? "Hide reel" : "Preview reel"}
          </button>
        )}
      </div>

      {packaged && showFinished && (
        <video
          src={reelMediaUrl(videoId, reel.index)}
          controls
          className="mt-3 w-full rounded-lg border border-zinc-800 bg-black"
          style={{ maxHeight: 420 }}
        />
      )}
    </div>
  );
}
