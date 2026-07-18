import { cn } from "@/lib/utils";

/**
 * Compact pipeline-progress readout: a segmented bar (one cell per stage, filled
 * in brand amber when done) with an "n/m" count. Replaces the old rows of tiny
 * per-stage chips on video and reel cards; the full stage list lives in the title
 * attribute for hover inspection.
 */
export function StageProgress({
  stages,
  done,
  className,
}: {
  /** Ordered stage names. */
  stages: readonly string[];
  /** Set of completed stage names. */
  done: ReadonlySet<string>;
  className?: string;
}) {
  const label = stages.map((s) => `${done.has(s) ? "✓" : "·"} ${s}`).join("\n");
  return (
    <div
      dir="ltr"
      className={cn("flex items-center gap-2", className)}
      title={label}
      aria-label={`${done.size} of ${stages.length} stages complete`}
    >
      <div className="flex h-1.5 flex-1 gap-0.5 overflow-hidden rounded-full">
        {stages.map((s) => (
          <span
            key={s}
            className={cn("flex-1", done.has(s) ? "bg-primary" : "bg-muted")}
          />
        ))}
      </div>
      <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
        {done.size}/{stages.length}
      </span>
    </div>
  );
}
