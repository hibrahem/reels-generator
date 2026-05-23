import { useEffect, useState } from "react";
import { subscribeJob, type JobEvent } from "../lib/api";

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
      ? "border-red-500/40 bg-red-500/5"
      : state === "done"
        ? "border-emerald-500/40 bg-emerald-500/5"
        : "border-indigo-500/40 bg-indigo-500/5";

  return (
    <div className={`rounded-xl border p-3 ${tone}`}>
      <div className="flex items-center gap-2">
        {state === "running" && (
          <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-indigo-400 border-t-transparent" />
        )}
        <span className="text-sm font-medium text-zinc-200">
          {state === "running" && (last ? `Running: ${last.stage}` : "Starting…")}
          {state === "done" && "✓ Done"}
          {state === "failed" && "✗ Failed"}
        </span>
        {last && state === "running" && (
          <span className="truncate text-xs text-zinc-400">{last.message}</span>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-red-300">{error}</p>}
      {events.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {events.map((e, i) => (
            <span
              key={i}
              className="rounded bg-zinc-800/80 px-1.5 py-0.5 text-[10px] text-zinc-300"
              title={e.message}
            >
              {e.stage}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
