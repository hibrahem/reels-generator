import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Maximize2, Trash2 } from "lucide-react";
import { api, fmtClock, type Reel, type ReelStage, type VideoDetail } from "../lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const REEL_STAGES: ReelStage[] = ["plan-layout", "cut", "reframe", "caption", "brand", "package"];

function ConfidenceBadge({ value }: { value: number }) {
  const tone =
    value >= 0.85
      ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
      : "bg-muted text-muted-foreground";
  return <span className={cn("rounded px-1.5 py-0.5 text-xs", tone)}>{value.toFixed(2)}</span>;
}

/**
 * Compact reel card for the video's reel list. Clicking anywhere on the card (or the Open button)
 * opens the focused {@link ReelDetail} editor, where trimming, processing, and stage redo live.
 * A Delete action is kept here too, for quickly removing a reel without opening the editor.
 */
export function ReelCard({
  videoId,
  reel,
  active,
  onOpen,
}: {
  videoId: string;
  reel: Reel;
  active: boolean;
  /** Open the focused per-reel detail editor. */
  onOpen: () => void;
}) {
  const qc = useQueryClient();
  const del = useMutation({
    mutationFn: () => api.deleteReel(videoId, reel.index),
    onSuccess: (updated: VideoDetail) => {
      qc.setQueryData(["video", videoId], updated);
      qc.invalidateQueries({ queryKey: ["videos"] });
    },
  });

  return (
    <div
      dir="rtl"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      title="Open reel editor"
      className={cn(
        "cursor-pointer rounded-xl border bg-card p-3 transition hover:border-primary/60 hover:bg-muted/30 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none",
        active ? "border-primary" : "border-border",
      )}
    >
      <div className="flex items-start justify-between gap-2" dir="ltr">
        <div className="flex items-center gap-2">
          <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
            {reel.index.toString().padStart(2, "0")}
          </span>
          <span className="text-xs text-muted-foreground">
            {fmtClock(reel.start)}–{fmtClock(reel.end)} · {reel.duration.toFixed(0)}s
          </span>
        </div>
        <div className="flex items-center gap-1">
          {reel.mode && (
            <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {reel.mode}
            </span>
          )}
          <ConfidenceBadge value={reel.confidence} />
        </div>
      </div>

      <h4 className="mt-2 font-medium" dir="auto">
        {reel.title}
      </h4>
      {reel.hook && (
        <p className="mt-1 text-sm text-muted-foreground" dir="auto">
          {reel.hook}
        </p>
      )}
      {reel.caption && (
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground" dir="auto">
          {reel.caption}
        </p>
      )}

      <div className="mt-2 flex flex-wrap gap-1" dir="ltr">
        {REEL_STAGES.map((s) => (
          <span
            key={s}
            title={s}
            className={cn(
              "rounded px-1.5 py-0.5 text-[10px]",
              reel.stages[s] ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
            )}
          >
            {s}
          </span>
        ))}
      </div>

      <div className="mt-3 flex gap-2" dir="ltr">
        <Button size="sm" onClick={onOpen} title="Open the focused reel editor">
          <Maximize2 />
          Open
        </Button>
        <Button
          size="sm"
          variant="destructive"
          className="ml-auto"
          disabled={del.isPending}
          title="Delete this reel"
          onClick={(e) => {
            e.stopPropagation(); // don't also open the detail view
            if (confirm(`Delete reel ${reel.index}?`)) del.mutate();
          }}
        >
          <Trash2 />
          {del.isPending ? "Deleting…" : "Delete"}
        </Button>
      </div>
    </div>
  );
}
