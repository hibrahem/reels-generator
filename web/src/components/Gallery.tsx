import { useQueries, useQuery } from "@tanstack/react-query";
import { api, fmtClock, reelMediaUrl } from "../lib/api";

export function Gallery({ onOpen }: { onOpen: (id: string) => void }) {
  const videos = useQuery({ queryKey: ["videos"], queryFn: api.listVideos });
  const ids = (videos.data ?? []).filter((v) => v.reel_count > 0).map((v) => v.id);
  const details = useQueries({
    queries: ids.map((id) => ({ queryKey: ["video", id], queryFn: () => api.getVideo(id) })),
  });

  const finished = details.flatMap((q, i) =>
    (q.data?.reels ?? [])
      .filter((r) => r.stages.package)
      .map((r) => ({ videoId: ids[i], filename: q.data!.filename, reel: r })),
  );

  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold text-zinc-100">Finished reels ({finished.length})</h2>
      {videos.isLoading && <p className="text-zinc-400">Loading…</p>}
      {!videos.isLoading && finished.length === 0 && (
        <div className="rounded-xl border border-dashed border-zinc-700 p-10 text-center text-zinc-400">
          No finished reels yet. Process some reels from a video's detail screen.
        </div>
      )}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {finished.map(({ videoId, reel }) => (
          <div key={`${videoId}-${reel.index}`} className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-2">
            <video
              src={reelMediaUrl(videoId, reel.index)}
              controls
              preload="metadata"
              className="aspect-[9/16] w-full rounded-lg bg-black"
            />
            <div className="mt-2 px-1" dir="auto">
              <p className="line-clamp-1 text-sm font-medium text-zinc-100">{reel.title}</p>
              <p className="text-xs text-zinc-500" dir="ltr">
                {fmtClock(reel.start)}–{fmtClock(reel.end)} · conf {reel.confidence.toFixed(2)}
              </p>
            </div>
            <div className="mt-2 flex gap-2 px-1" dir="ltr">
              <a
                href={reelMediaUrl(videoId, reel.index)}
                download={reel.output_filename}
                className="rounded-lg bg-indigo-600/80 px-2 py-1 text-xs text-white transition hover:bg-indigo-500"
              >
                Download
              </a>
              <button
                onClick={() => onOpen(videoId)}
                className="rounded-lg bg-zinc-800 px-2 py-1 text-xs text-zinc-200 transition hover:bg-zinc-700"
              >
                Open video
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
