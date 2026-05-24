import { useQueries, useQuery } from "@tanstack/react-query";
import { Download, Film } from "lucide-react";
import { api, fmtClock, reelMediaUrl } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

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
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border p-12 text-center">
          <span className="flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Film className="size-6" />
          </span>
          <p className="max-w-sm text-sm text-muted-foreground">
            No finished reels yet. Process some reels from a video&apos;s detail screen.
          </p>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {finished.map(({ videoId, reel }) => (
          <Card key={`${videoId}-${reel.index}`} className="gap-2 p-2">
            <video
              src={reelMediaUrl(videoId, reel.index)}
              controls
              preload="metadata"
              className="aspect-[9/16] w-full rounded-lg bg-black"
            />
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
        ))}
      </div>
    </div>
  );
}
