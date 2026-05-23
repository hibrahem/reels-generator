import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, fmtClock, mediaUrl, type Reel } from "../lib/api";
import { ReelCard } from "./ReelCard";
import { TranscriptView } from "./TranscriptView";

export function VideoDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const playUntilRef = useRef<number | null>(null); // auto-stop boundary for "Play span"
  const [currentTime, setCurrentTime] = useState(0);
  const [activeReel, setActiveReel] = useState<number | null>(null);
  const [loopSpan, setLoopSpan] = useState(false);
  const [bottomTab, setBottomTab] = useState<"transcript" | "summary">("transcript");

  const detail = useQuery({ queryKey: ["video", id], queryFn: () => api.getVideo(id) });
  const transcript = useQuery({
    queryKey: ["transcript", id],
    queryFn: () => api.getTranscript(id),
    retry: false,
  });

  function seekTo(t: number, play = true) {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = t;
    if (play) void v.play();
  }

  function playReel(reel: Reel) {
    setActiveReel(reel.index);
    playUntilRef.current = reel.end; // stop at the reel's end to simulate the finished clip
    seekTo(reel.start);
  }

  function onTimeUpdate(e: React.SyntheticEvent<HTMLVideoElement>) {
    const v = e.currentTarget;
    setCurrentTime(v.currentTime);
    const until = playUntilRef.current;
    if (until != null && v.currentTime >= until) {
      if (loopSpan && activeReel != null) {
        const reel = detail.data?.reels.find((r) => r.index === activeReel);
        if (reel) {
          v.currentTime = reel.start; // restart the span
          return;
        }
      }
      v.pause();
      playUntilRef.current = null;
    }
  }

  // Manual scrubbing cancels the auto-stop boundary so the user can watch freely.
  function onSeeking(e: React.SyntheticEvent<HTMLVideoElement>) {
    const v = e.currentTarget;
    const until = playUntilRef.current;
    if (until != null && (v.currentTime < (currentTime - 0.4) || v.currentTime > until + 0.1)) {
      playUntilRef.current = null;
      setActiveReel(null);
    }
  }

  if (detail.isLoading) return <p className="text-zinc-400">Loading…</p>;
  if (detail.error) return <p className="text-red-400">Failed: {String(detail.error)}</p>;
  const d = detail.data!;

  return (
    <div>
      <button onClick={onBack} className="mb-3 text-sm text-indigo-400 hover:text-indigo-300">
        ← Library
      </button>
      <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="text-lg font-semibold text-zinc-100">{d.filename}</h2>
        <span className="text-sm text-zinc-400">
          {d.width}×{d.height} · {d.fps?.toFixed(0)}fps · {fmtClock(d.duration_seconds ?? 0)} ·{" "}
          {d.reels.length} reels
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        {/* Player + bottom tabs */}
        <div className="min-w-0">
          <div className="overflow-hidden rounded-xl border border-zinc-800 bg-black">
            <video
              ref={videoRef}
              src={mediaUrl(id)}
              controls
              className="aspect-video w-full bg-black"
              onTimeUpdate={onTimeUpdate}
              onSeeking={onSeeking}
            />
          </div>

          <label className="mt-2 flex items-center gap-2 text-sm text-zinc-400">
            <input
              type="checkbox"
              checked={loopSpan}
              onChange={(e) => setLoopSpan(e.target.checked)}
              className="accent-indigo-500"
            />
            Loop the played span
          </label>

          <div className="mt-4 flex gap-1">
            {(["transcript", "summary"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setBottomTab(t)}
                className={`rounded-lg px-3 py-1.5 text-sm capitalize transition ${
                  bottomTab === t ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="mt-3">
            {bottomTab === "transcript" &&
              (transcript.data ? (
                <TranscriptView
                  segments={transcript.data.segments}
                  currentTime={currentTime}
                  onSeek={(t) => seekTo(t)}
                />
              ) : (
                <p className="text-sm text-zinc-500">No transcript yet — run the transcribe stage.</p>
              ))}
            {bottomTab === "summary" && (
              <div className="space-y-2 text-sm text-zinc-300">
                <p>Stages done: {d.completed_stages.join(", ") || "—"}</p>
                {d.warnings.length > 0 && (
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
                    <p className="mb-1 font-medium text-amber-300">{d.warnings.length} warnings</p>
                    <ul className="list-inside list-disc text-amber-200/80">
                      {d.warnings.slice(0, 12).map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Reels panel */}
        <div className="min-w-0">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Reels ({d.reels.length})
          </h3>
          <div className="flex flex-col gap-3">
            {d.reels.length === 0 && (
              <p className="text-sm text-zinc-500">No reels selected yet — run the select stage.</p>
            )}
            {d.reels.map((r) => (
              <ReelCard
                key={r.index}
                videoId={id}
                reel={r}
                active={activeReel === r.index}
                onPlaySpan={() => playReel(r)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
