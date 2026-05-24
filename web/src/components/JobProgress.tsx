import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import { subscribeJob, type JobEvent } from "../lib/api";
import { cn } from "@/lib/utils";

export function JobProgress({ jobId, onDone }: { jobId: string; onDone: () => void }) {
  const [events, setEvents] = useState<JobEvent[]>([]);
  const [state, setState] = useState<"running" | "done" | "failed">("running");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEvents([]);
    setState("running");
    setError(null);
    const stop = subscribeJob(jobId, {
      onProgress: (e) => setEvents((prev) => [...prev, e]),
      onEnd: (s, err) => {
        setState(s as "done" | "failed");
        setError(err);
        onDone();
      },
    });
    return stop;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const last = events[events.length - 1];
  const tone =
    state === "failed"
      ? "border-destructive/40 bg-destructive/10"
      : state === "done"
        ? "border-emerald-500/40 bg-emerald-500/5"
        : "border-primary/40 bg-primary/5";

  return (
    <div className={cn("rounded-xl border p-3", tone)}>
      <div className="flex items-center gap-2">
        {state === "running" && <Loader2 className="size-4 shrink-0 animate-spin text-primary" />}
        {state === "done" && (
          <CheckCircle2 className="size-4 shrink-0 text-emerald-500 dark:text-emerald-400" />
        )}
        {state === "failed" && <XCircle className="size-4 shrink-0 text-destructive" />}
        <span className="text-sm font-medium text-foreground">
          {state === "running" && (last ? `Running: ${last.stage}` : "Starting…")}
          {state === "done" && "Done"}
          {state === "failed" && "Failed"}
        </span>
        {last && state === "running" && (
          <span className="truncate text-xs text-muted-foreground">{last.message}</span>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-destructive">{error}</p>}
      {events.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {events.map((e, i) => {
            const isCurrent = state === "running" && i === events.length - 1;
            return (
              <span
                key={i}
                title={e.message}
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10px]",
                  isCurrent ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
                )}
              >
                {e.stage}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
