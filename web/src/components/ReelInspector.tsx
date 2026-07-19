import { useState } from "react";
import { ArrowLeft, Download, Eye, Loader2, Scissors, Trash2 } from "lucide-react";
import { fmtClock, reelMediaUrl, type Reel, type ReelStage } from "../lib/api";
import { Button } from "@/components/ui/button";
import { ReelPipeline } from "./ReelPipeline";

export type ReelEditForm = {
  start: number;
  end: number;
  title: string;
  hook: string;
  caption: string;
};

const fieldCls =
  "w-full rounded-lg border border-input bg-background px-2 py-1 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

/**
 * Right-rail inspector for the reel selected in the unified editor. Presentational:
 * the edit form and all mutations live in {@link VideoDetail}, which also drives the
 * shared player/timeline/transcript from the same form state.
 */
export function ReelInspector({
  videoId,
  reel,
  form,
  onFormChange,
  dirty,
  timesChanged,
  saving,
  saveError,
  deleting,
  busy,
  onSave,
  onReset,
  onDelete,
  onProcess,
  onRedoStage,
  onClose,
}: {
  videoId: string;
  reel: Reel;
  form: ReelEditForm;
  onFormChange: (patch: Partial<ReelEditForm>) => void;
  dirty: boolean;
  timesChanged: boolean;
  saving: boolean;
  saveError: unknown;
  deleting: boolean;
  busy: boolean;
  onSave: () => void;
  onReset: () => void;
  onDelete: () => void;
  onProcess: () => void;
  onRedoStage: (stage: ReelStage, cascade: boolean) => void;
  onClose: () => void;
}) {
  const [showFinished, setShowFinished] = useState(false);
  const packaged = reel.stages.package;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <button
          onClick={onClose}
          title="Back to the reel list (Esc)"
          className="inline-flex items-center gap-1 rounded-md text-sm text-muted-foreground transition hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <ArrowLeft className="size-4" />
          All reels
        </button>
        <span className="rounded bg-primary/15 px-1.5 py-0.5 font-mono text-xs text-primary">
          {reel.index.toString().padStart(2, "0")}
        </span>
        <span className="text-xs text-muted-foreground" dir="ltr">
          {fmtClock(form.start)}–{fmtClock(form.end)} · {(form.end - form.start).toFixed(1)}s
        </span>
      </div>

      <div className="rounded-xl border border-primary/40 bg-card p-4">
        <h3 className="mb-3 font-heading text-xs font-semibold uppercase tracking-wider text-primary">
          Details
        </h3>
        <div className="space-y-2" dir="ltr">
          <input
            value={form.title}
            dir="auto"
            onChange={(e) => onFormChange({ title: e.target.value })}
            placeholder="title"
            className={fieldCls}
          />
          <input
            value={form.hook}
            dir="auto"
            onChange={(e) => onFormChange({ hook: e.target.value })}
            placeholder="hook"
            className={fieldCls}
          />
          <textarea
            value={form.caption}
            dir="auto"
            onChange={(e) => onFormChange({ caption: e.target.value })}
            placeholder="caption"
            rows={2}
            className={fieldCls}
          />
        </div>
        {timesChanged && (
          <p className="mt-2 text-[11px] text-muted-foreground">
            Saving re-snaps to word boundaries and clears this reel's renders.
          </p>
        )}
        <div className="mt-3 flex gap-2">
          <Button size="sm" onClick={onSave} disabled={!dirty || saving}>
            <Scissors />
            {saving ? "Saving…" : "Save edits"}
          </Button>
          {dirty && (
            <Button size="sm" variant="secondary" onClick={onReset}>
              Reset
            </Button>
          )}
          <Button
            size="icon-sm"
            variant="ghost"
            className="ml-auto text-muted-foreground hover:bg-destructive/15 hover:text-destructive"
            disabled={deleting}
            title="Delete this reel"
            onClick={onDelete}
          >
            {deleting ? <Loader2 className="animate-spin" /> : <Trash2 />}
          </Button>
        </div>
        {saveError != null && (
          <p className="mt-2 text-xs text-destructive">{String(saveError)}</p>
        )}
      </div>

      <ReelPipeline
        reel={reel}
        jobId={null}
        busy={busy}
        onProcess={onProcess}
        onRedoStage={onRedoStage}
        onJobDone={() => {}}
      />

      {packaged && (
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="mb-3 font-heading text-xs font-semibold uppercase tracking-wider text-primary">
            Output
          </h3>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => setShowFinished((v) => !v)}>
              <Eye />
              {showFinished ? "Hide reel" : "Preview reel"}
            </Button>
            <Button asChild size="sm" variant="secondary">
              <a
                href={reelMediaUrl(videoId, reel.index, reel.rendered_at)}
                download={reel.output_filename}
              >
                <Download />
                Download
              </a>
            </Button>
          </div>
          {showFinished && (
            <video
              src={reelMediaUrl(videoId, reel.index, reel.rendered_at)}
              controls
              className="mt-3 w-full rounded-lg border border-border bg-black"
              style={{ maxHeight: 480 }}
            />
          )}
        </div>
      )}
    </div>
  );
}
