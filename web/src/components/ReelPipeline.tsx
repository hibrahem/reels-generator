import { CheckCircle2, ChevronsRight, Circle, Play, RotateCw } from "lucide-react";
import { type Reel, type ReelStage } from "../lib/api";
import { Button } from "@/components/ui/button";
import { JobProgress } from "./JobProgress";
import { cn } from "@/lib/utils";

const REEL_STAGES: ReelStage[] = ["plan-layout", "cut", "reframe", "caption", "brand", "package"];

/**
 * Per-reel pipeline view: the six reel-scoped stages as a vertical pipeline, each with its
 * completion status and two redo actions for just this reel — "redo" re-runs only that one
 * stage, while "redo to end" cascades from that stage through package so stale downstream
 * outputs get regenerated too. The cascade action is hidden on the final (package) stage,
 * where it would be identical to a single-stage redo. "Process this reel" runs the full
 * plan-layout → package chain. Live progress streams via the shared JobProgress card while a
 * job is in flight.
 */
export function ReelPipeline({
  reel,
  jobId,
  busy,
  onProcess,
  onRedoStage,
  onJobDone,
}: {
  reel: Reel;
  jobId: string | null;
  busy: boolean;
  onProcess: () => void;
  onRedoStage: (stage: ReelStage, cascade: boolean) => void;
  onJobDone: () => void;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Pipeline
        </h3>
        <Button
          size="sm"
          onClick={onProcess}
          disabled={busy}
          title="Resume from this reel's first unfinished stage (use a stage's redo to re-run just that one)"
        >
          <Play />
          Process this reel
        </Button>
      </div>

      <ol className="space-y-1">
        {REEL_STAGES.map((stage, i) => {
          const done = reel.stages[stage];
          return (
            <li
              key={stage}
              className="flex items-center gap-3 rounded-lg px-2 py-1.5 hover:bg-muted/40"
            >
              <span className="w-4 text-center font-mono text-[11px] text-muted-foreground">
                {i + 1}
              </span>
              {done ? (
                <CheckCircle2 className="size-4 shrink-0 text-emerald-500 dark:text-emerald-400" />
              ) : (
                <Circle className="size-4 shrink-0 text-muted-foreground/50" />
              )}
              <span
                className={cn(
                  "flex-1 text-sm",
                  done ? "text-foreground" : "text-muted-foreground",
                )}
              >
                {stage}
              </span>
              <div className="flex items-center gap-0.5">
                <button
                  type="button"
                  onClick={() => onRedoStage(stage, false)}
                  disabled={busy}
                  title={`Re-run only the ${stage} stage for this reel`}
                  className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-40"
                >
                  <RotateCw className="size-3" />
                  redo
                </button>
                {i < REEL_STAGES.length - 1 && (
                  <button
                    type="button"
                    onClick={() => onRedoStage(stage, true)}
                    disabled={busy}
                    title={`Re-run ${stage} and every stage after it (through package) for this reel`}
                    className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-muted-foreground transition hover:bg-muted hover:text-foreground disabled:opacity-40"
                  >
                    <ChevronsRight className="size-3" />
                    redo to end
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {jobId && (
        <div className="mt-3">
          <JobProgress key={jobId} jobId={jobId} onDone={onJobDone} />
        </div>
      )}
    </div>
  );
}
