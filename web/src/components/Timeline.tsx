import { type Reel } from "../lib/api";

export function Timeline({
  reels,
  duration,
  currentTime,
  activeReel,
  onPlayReel,
  onSeek,
}: {
  reels: Reel[];
  duration: number;
  currentTime: number;
  activeReel: number | null;
  onPlayReel: (r: Reel) => void;
  onSeek: (t: number) => void;
}) {
  const pct = (t: number) => (duration > 0 ? Math.max(0, Math.min(100, (t / duration) * 100)) : 0);

  function seekFromClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    onSeek(ratio * duration);
  }

  return (
    <div className="mt-3">
      <div
        onClick={seekFromClick}
        className="relative h-11 w-full cursor-pointer rounded-lg border border-zinc-800 bg-zinc-900"
        title="Click to seek"
      >
        {reels.map((r) => {
          const active = activeReel === r.index;
          return (
            <button
              key={r.index}
              onClick={(e) => {
                e.stopPropagation();
                onPlayReel(r);
              }}
              title={`${r.index}. ${r.title}`}
              className={`absolute top-1 flex h-9 items-center justify-center overflow-hidden rounded text-[10px] font-medium text-white transition ${
                active ? "bg-indigo-500 ring-2 ring-indigo-300" : "bg-indigo-500/55 hover:bg-indigo-500/80"
              }`}
              style={{ left: `${pct(r.start)}%`, width: `${Math.max(pct(r.end - r.start), 1.2)}%` }}
            >
              {r.index}
            </button>
          );
        })}
        {/* playhead */}
        <div
          className="pointer-events-none absolute -top-0.5 h-12 w-0.5 bg-white/90"
          style={{ left: `${pct(currentTime)}%` }}
        />
      </div>
      <p className="mt-1 text-[11px] text-zinc-500">
        {reels.length} reels on the timeline · click a block to play that span, or the track to seek
      </p>
    </div>
  );
}
