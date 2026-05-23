import { posterUrl, STAGES, type VideoSummary } from "../lib/api";

function fmtDuration(s: number | null): string {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function VideoCard({ video, onOpen }: { video: VideoSummary; onOpen: (id: string) => void }) {
  const done = new Set(video.completed_stages);
  return (
    <button
      onClick={() => onOpen(video.id)}
      className="flex w-full flex-col gap-3 overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/60 text-left transition hover:border-zinc-600 hover:bg-zinc-900"
    >
      {video.ingested ? (
        <img
          src={posterUrl(video.id)}
          alt=""
          loading="lazy"
          className="aspect-video w-full bg-zinc-800 object-cover"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />
      ) : (
        <div className="flex aspect-video w-full items-center justify-center bg-zinc-800/50 text-3xl">
          🎬
        </div>
      )}
      <div className="flex flex-col gap-3 p-4 pt-0">
      <div className="flex items-start justify-between gap-2">
        <h3 className="line-clamp-2 font-medium text-zinc-100">{video.filename}</h3>
        {!video.ingested && (
          <span className="shrink-0 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-300">
            not ingested
          </span>
        )}
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-zinc-400">
        <span>{fmtDuration(video.duration_seconds)}</span>
        {video.width && <span>{video.width}×{video.height}</span>}
        {video.fps && <span>{video.fps.toFixed(0)}fps</span>}
        <span>{video.reel_count} reels</span>
        {video.warning_count > 0 && (
          <span className="text-amber-400">{video.warning_count} ⚠</span>
        )}
      </div>

      <div className="flex flex-wrap gap-1">
        {STAGES.map((s) => (
          <span
            key={s}
            title={s}
            className={`rounded px-1.5 py-0.5 text-[10px] ${
              done.has(s)
                ? "bg-emerald-500/20 text-emerald-300"
                : "bg-zinc-800 text-zinc-500"
            }`}
          >
            {s}
          </span>
        ))}
      </div>
      </div>
    </button>
  );
}
