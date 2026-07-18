import { useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Download, Film, Play } from "lucide-react";
import { api, fmtClock, reelMediaUrl } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "./EmptyState";

export function Gallery({ onOpen }: { onOpen: (id: string) => void }) {
  const videos = useQuery({ queryKey: ["videos"], queryFn: api.listVideos });
  // Only the clicked reel gets a playing <video controls>; the rest stay as
  // lightweight poster frames so a large gallery doesn't render dozens of players.
  const [playing, setPlaying] = useState<string | null>(null);
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
      <div className="mb-6">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Finished reels</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {finished.length} {finished.length === 1 ? "reel" : "reels"} ready to download
        </p>
      </div>

      {videos.isLoading && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="aspect-[9/16] animate-pulse rounded-xl bg-muted/50" />
          ))}
        </div>
      )}

      {!videos.isLoading && finished.length === 0 && (
        <EmptyState icon={Film}>
          No finished reels yet. Process some reels from a video&apos;s detail screen.
        </EmptyState>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {finished.map(({ videoId, reel }) => {
          const key = `${videoId}-${reel.index}`;
          const isPlaying = playing === key;
          return (
            <Card key={key} className="gap-2 p-2">
              <div className="relative overflow-hidden rounded-lg bg-black">
                <video
                  src={reelMediaUrl(videoId, reel.index)}
                  controls={isPlaying}
                  autoPlay={isPlaying}
                  preload="metadata"
                  className="aspect-[9/16] w-full"
                />
                {!isPlaying && (
                  <button
                    type="button"
                    onClick={() => setPlaying(key)}
                    aria-label={`Play ${reel.title}`}
                    className="group absolute inset-0 flex items-center justify-center bg-black/20 transition hover:bg-black/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    <span className="flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition group-hover:scale-110">
                      <Play className="ml-0.5 size-5" fill="currentColor" />
                    </span>
                  </button>
                )}
              </div>
              <div className="px-1" dir="auto">
                <p className="line-clamp-1 text-sm font-medium">{reel.title}</p>
                <p className="text-xs text-muted-foreground" dir="ltr">
                  {fmtClock(reel.start)}–{fmtClock(reel.end)} · conf {reel.confidence.toFixed(2)}
                </p>
              </div>
              <div className="flex gap-2 px-1" dir="ltr">
                <Button asChild size="sm">
                  <a href={reelMediaUrl(videoId, reel.index)} download={reel.output_filename}>
                    <Download />
                    Download
                  </a>
                </Button>
                <Button variant="secondary" size="sm" onClick={() => onOpen(videoId)}>
                  Open video
                </Button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
