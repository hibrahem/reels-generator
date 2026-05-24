import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Eye, Pencil, Play, Settings2, Trash2 } from "lucide-react";
import { api, fmtClock, reelMediaUrl, type Reel, type ReelStage, type VideoDetail } from "../lib/api";
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

export function ReelCard({
  videoId,
  reel,
  active,
  onPlaySpan,
  onProcess,
}: {
  videoId: string;
  reel: Reel;
  active: boolean;
  onPlaySpan: () => void;
  onProcess: () => void;
}) {
  const qc = useQueryClient();
  const [showFinished, setShowFinished] = useState(false);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    start: reel.start,
    end: reel.end,
    title: reel.title,
    hook: reel.hook,
    caption: reel.caption,
  });
  const packaged = reel.stages.package;

  const onSaved = (updated: VideoDetail) => {
    qc.setQueryData(["video", videoId], updated);
    qc.invalidateQueries({ queryKey: ["videos"] });
  };
  const saveEdit = useMutation({
    mutationFn: () => api.editReel(videoId, reel.index, form),
    onSuccess: (u) => {
      onSaved(u);
      setEditing(false);
    },
  });
  const del = useMutation({
    mutationFn: () => api.deleteReel(videoId, reel.index),
    onSuccess: onSaved,
  });

  function openEdit() {
    setForm({ start: reel.start, end: reel.end, title: reel.title, hook: reel.hook, caption: reel.caption });
    setEditing(true);
  }

  const fieldCls =
    "w-full rounded-lg border border-input bg-background px-2 py-1 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

  return (
    <div
      dir="rtl"
      className={cn(
        "rounded-xl border bg-card p-3 transition",
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

      {!editing ? (
        <>
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
        </>
      ) : (
        <div className="mt-2 space-y-2" dir="ltr">
          <div className="flex gap-2">
            <label className="flex-1 text-xs text-muted-foreground">
              start (s)
              <input
                type="number"
                step="0.1"
                value={form.start}
                onChange={(e) => setForm({ ...form, start: Number(e.target.value) })}
                className={fieldCls}
              />
            </label>
            <label className="flex-1 text-xs text-muted-foreground">
              end (s)
              <input
                type="number"
                step="0.1"
                value={form.end}
                onChange={(e) => setForm({ ...form, end: Number(e.target.value) })}
                className={fieldCls}
              />
            </label>
          </div>
          <input
            value={form.title}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
            placeholder="title"
            className={fieldCls}
          />
          <input
            dir="auto"
            value={form.hook}
            onChange={(e) => setForm({ ...form, hook: e.target.value })}
            placeholder="hook"
            className={fieldCls}
          />
          <textarea
            dir="auto"
            value={form.caption}
            onChange={(e) => setForm({ ...form, caption: e.target.value })}
            placeholder="caption"
            rows={2}
            className={fieldCls}
          />
          <p className="text-[11px] text-muted-foreground">
            Changing start/end re-snaps to word boundaries and clears this reel's renders.
          </p>
        </div>
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

      <div className="mt-3 flex flex-wrap gap-2" dir="ltr">
        {!editing ? (
          <>
            <Button size="sm" variant="secondary" onClick={onPlaySpan}>
              <Play />
              Play span
            </Button>
            <Button size="sm" variant="secondary" onClick={onProcess} title="Render this reel">
              <Settings2 />
              Process
            </Button>
            <Button size="sm" variant="secondary" onClick={openEdit}>
              <Pencil />
              Edit
            </Button>
            {packaged && (
              <Button size="sm" onClick={() => setShowFinished((v) => !v)}>
                <Eye />
                {showFinished ? "Hide reel" : "Preview reel"}
              </Button>
            )}
            {packaged && (
              <Button asChild size="sm" variant="secondary">
                <a href={reelMediaUrl(videoId, reel.index)} download={reel.output_filename}>
                  <Download />
                  Download
                </a>
              </Button>
            )}
          </>
        ) : (
          <>
            <Button size="sm" onClick={() => saveEdit.mutate()} disabled={saveEdit.isPending}>
              {saveEdit.isPending ? "Saving…" : "Save"}
            </Button>
            <Button size="sm" variant="secondary" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="destructive"
              className="ml-auto"
              onClick={() => {
                if (confirm(`Delete reel ${reel.index}?`)) del.mutate();
              }}
            >
              <Trash2 />
              Delete
            </Button>
          </>
        )}
      </div>

      {packaged && showFinished && !editing && (
        <video
          src={reelMediaUrl(videoId, reel.index)}
          controls
          className="mt-3 w-full rounded-lg border border-border bg-black"
          style={{ maxHeight: 420 }}
        />
      )}
    </div>
  );
}
