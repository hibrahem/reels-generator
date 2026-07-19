import { useState } from "react";
import { Check, Eye, Play } from "lucide-react";
import { STAGES, type VideoDetail } from "../lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type StepState = "done" | "current" | "pending";

/**
 * Guided pipeline flow for one video: Transcribe → Select → Review → Render → Export.
 * The step states derive from completed stages, so the stepper doubles as a progress
 * readout; one primary action always targets the next thing to do. The raw stage-range
 * controls (from/to + preview transcode) live behind the Advanced disclosure.
 */
export function PipelineStepper({
  detail,
  busy,
  onRun,
  onPreview,
  onExport,
}: {
  detail: VideoDetail;
  busy: boolean;
  onRun: (fromStage: string, toStage: string) => void;
  onPreview: () => void;
  onExport?: () => void;
}) {
  const [fromStage, setFromStage] = useState("plan-layout");
  const [toStage, setToStage] = useState("package");

  const done = new Set(detail.completed_stages);
  const transcribed = done.has("transcribe");
  const selectDone = done.has("select");
  const reels = detail.reels;
  const packagedCount = reels.filter((r) => r.stages.package).length;
  const allPackaged = reels.length > 0 && packagedCount === reels.length;

  const steps: { label: string; sub: string; state: StepState }[] = [
    {
      label: "Transcribe",
      sub: transcribed ? "speech → text done" : "speech → text",
      state: transcribed ? "done" : "current",
    },
    {
      label: "Select",
      sub: selectDone ? `${reels.length} reels planned` : "LLM picks the moments",
      state: selectDone ? "done" : transcribed ? "current" : "pending",
    },
    {
      label: "Review",
      sub: "trim and polish (optional)",
      state: allPackaged
        ? "done"
        : selectDone && packagedCount === 0
          ? "current"
          : "pending",
    },
    {
      label: "Render",
      sub: reels.length > 0 ? `${packagedCount}/${reels.length} rendered` : "cut, caption, brand",
      state: allPackaged ? "done" : packagedCount > 0 ? "current" : "pending",
    },
    {
      label: "Export",
      sub: "download from the Gallery",
      state: allPackaged ? "current" : "pending",
    },
  ];

  const primary = !transcribed
    ? { label: "Transcribe", run: () => onRun("ingest", "transcribe") }
    : !selectDone
      ? { label: "Select reels", run: () => onRun("select", "select") }
      : !allPackaged
        ? { label: "Render all reels", run: () => onRun("plan-layout", "package") }
        : onExport
          ? { label: "View in Gallery", run: onExport, isNav: true as const }
          : null;

  const selectClass =
    "h-8 rounded-lg border border-input bg-background px-2 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

  return (
    <div className="mb-4 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-4">
        <ol className="flex min-w-0 flex-1 flex-wrap items-start gap-x-1 gap-y-2">
          {steps.map((s, i) => (
            <li key={s.label} className="flex items-start">
              {i > 0 && (
                <span
                  className={cn(
                    "mx-1 mt-3 h-px w-4 sm:w-7",
                    s.state === "done" || steps[i - 1].state === "done"
                      ? "bg-primary/60"
                      : "bg-border",
                  )}
                />
              )}
              <div className="flex flex-col items-center gap-1 text-center">
                <span
                  className={cn(
                    "flex size-6 items-center justify-center rounded-full text-[11px] font-semibold",
                    s.state === "done"
                      ? "bg-primary text-primary-foreground"
                      : s.state === "current"
                        ? "bg-primary/15 text-primary ring-1 ring-primary"
                        : "bg-muted text-muted-foreground",
                  )}
                >
                  {s.state === "done" ? <Check className="size-3.5" /> : i + 1}
                </span>
                <span
                  className={cn(
                    "text-xs font-medium",
                    s.state === "pending" ? "text-muted-foreground" : "text-foreground",
                  )}
                >
                  {s.label}
                </span>
                <span className="max-w-24 text-[10px] leading-tight text-muted-foreground">
                  {s.sub}
                </span>
              </div>
            </li>
          ))}
        </ol>
        {primary && (
          <Button onClick={primary.run} disabled={busy && !("isNav" in primary)}>
            <Play />
            {primary.label}
          </Button>
        )}
      </div>

      <details className="mt-3 border-t border-border pt-2">
        <summary className="cursor-pointer text-xs text-muted-foreground transition hover:text-foreground">
          Advanced — run an exact stage range
        </summary>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            from
            <select
              value={fromStage}
              onChange={(e) => setFromStage(e.target.value)}
              className={selectClass}
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
            to
            <select
              value={toStage}
              onChange={(e) => setToStage(e.target.value)}
              className={selectClass}
            >
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <Button size="sm" variant="secondary" onClick={() => onRun(fromStage, toStage)} disabled={busy}>
            <Play />
            Run
          </Button>
          <Button
            size="sm"
            variant="secondary"
            onClick={onPreview}
            disabled={busy}
            title="Transcode a browser-friendly preview (audio in Chrome)"
          >
            <Eye />
            Generate preview
          </Button>
        </div>
      </details>
    </div>
  );
}
