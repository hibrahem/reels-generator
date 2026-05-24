import { Loader2 } from "lucide-react";
import { posterUrl, STAGES, type VideoSummary } from "../lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function fmtDuration(s: number | null): string {
  if (s == null) return "—";
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export function VideoCard({
  video,
  onOpen,
  processing = false,
}: {
  video: VideoSummary;
  onOpen: (id: string) => void;
  processing?: boolean;
}) {
  const done = new Set(video.completed_stages);
  return (
    <Card
      role="button"
      tabIndex={0}
      aria-label={`Open ${video.filename}`}
      onClick={() => onOpen(video.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen(video.id);
        }
      }}
      className="relative cursor-pointer gap-0 py-0 transition hover:ring-foreground/25 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {processing && (
        <Badge className="absolute left-2 top-2 z-10 gap-1 shadow">
          <Loader2 className="size-3 animate-spin" />
          Processing
        </Badge>
      )}
      {video.ingested ? (
        <img
          src={posterUrl(video.id)}
          alt=""
          loading="lazy"
          className="aspect-video w-full bg-muted object-cover"
          onError={(e) => (e.currentTarget.style.display = "none")}
        />
      ) : (
        <div className="flex aspect-video w-full items-center justify-center bg-muted text-3xl">
          🎬
        </div>
      )}

      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-2 font-medium leading-snug">{video.filename}</h3>
          {!video.ingested && (
            <Badge
              variant="outline"
              className="shrink-0 border-amber-500/40 text-amber-600 dark:text-amber-400"
            >
              not ingested
            </Badge>
          )}
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
          <span>{fmtDuration(video.duration_seconds)}</span>
          {video.width && (
            <span>
              {video.width}×{video.height}
            </span>
          )}
          {video.fps && <span>{video.fps.toFixed(0)}fps</span>}
          <span>{video.reel_count} reels</span>
          {video.warning_count > 0 && (
            <span className="text-amber-600 dark:text-amber-400">{video.warning_count} ⚠</span>
          )}
        </div>

        <div className="flex flex-wrap gap-1">
          {STAGES.map((s) => (
            <span
              key={s}
              title={s}
              className={cn(
                "rounded px-1.5 py-0.5 text-[10px]",
                done.has(s)
                  ? "bg-primary/15 text-primary"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {s}
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}
