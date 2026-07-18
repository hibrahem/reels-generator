import { Loader2 } from "lucide-react";
import { posterUrl, STAGES, type VideoSummary } from "../lib/api";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Logo } from "./Logo";
import { StageProgress } from "./StageProgress";

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
      className="relative cursor-pointer gap-0 py-0 transition hover:ring-primary/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      {processing && (
        <Badge className="absolute left-2 top-2 z-10 gap-1 shadow">
          <Loader2 className="size-3 animate-spin" />
          Processing
        </Badge>
      )}
      <div className="relative">
        {video.ingested ? (
          <img
            src={posterUrl(video.id)}
            alt=""
            loading="lazy"
            className="aspect-video w-full bg-muted object-cover"
            onError={(e) => (e.currentTarget.style.display = "none")}
          />
        ) : (
          <div className="flex aspect-video w-full items-center justify-center bg-muted">
            <Logo className="size-10 text-primary/40" />
          </div>
        )}
        <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[11px] text-white backdrop-blur-sm">
          {fmtDuration(video.duration_seconds)}
        </span>
      </div>

      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="line-clamp-2 font-medium leading-snug">{video.filename}</h3>
          {!video.ingested && (
            <Badge variant="outline" className="shrink-0 border-primary/40 text-primary">
              not ingested
            </Badge>
          )}
        </div>

        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-muted-foreground">
          {video.width && (
            <span>
              {video.width}×{video.height}
            </span>
          )}
          {video.fps && <span>{video.fps.toFixed(0)} fps</span>}
          <span className={video.reel_count > 0 ? "text-foreground" : undefined}>
            {video.reel_count} {video.reel_count === 1 ? "reel" : "reels"}
          </span>
          {video.warning_count > 0 && (
            <span className="text-primary">{video.warning_count} ⚠</span>
          )}
        </div>

        <StageProgress stages={STAGES} done={done} />
      </div>
    </Card>
  );
}
