import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, fmtClock, reelMediaUrl, type Reel, type ReelStage, type VideoDetail } from "../lib/api";

const REEL_STAGES: ReelStage[] = ["plan-layout", "cut", "reframe", "caption", "brand", "package"];

function ConfidenceBadge({ value }: { value: number }) {
  const tone =
    value >= 0.85 ? "bg-emerald-500/20 text-emerald-300" : "bg-zinc-700/60 text-zinc-300";
  return <span className={`rounded px-1.5 py-0.5 text-xs ${tone}`}>{value.toFixed(2)}</span>;
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

  const fieldCls = "w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200";

  return (
    <div
      dir="rtl"
      className={`rounded-xl border bg-zinc-900/60 p-3 transition ${
        active ? "border-indigo-500" : "border-zinc-800"
      }`}
    >
      <div className="flex items-start justify-between gap-2" dir="ltr">
        <div className="flex items-center gap-2">
          <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-400">
            {reel.index.toString().padStart(2, "0")}
          </span>
          <span className="text-xs text-zinc-400">
            {fmtClock(reel.start)}–{fmtClock(reel.end)} · {reel.duration.toFixed(0)}s
          </span>
        </div>
        <div className="flex items-center gap-1">
          {reel.mode && (
            <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-400">
              {reel.mode}
            </span>
          )}
          <ConfidenceBadge value={reel.confidence} />
        </div>
      </div>

      {!editing ? (
        <>
          <h4 className="mt-2 font-medium text-zinc-100" dir="auto">{reel.title}</h4>
          {reel.hook && <p className="mt-1 text-sm text-zinc-300" dir="auto">{reel.hook}</p>}
          {reel.caption && (
            <p className="mt-1 line-clamp-2 text-xs text-zinc-500" dir="auto">{reel.caption}</p>
          )}
        </>
      ) : (
        <div className="mt-2 space-y-2" dir="ltr">
          <div className="flex gap-2">
            <label className="flex-1 text-xs text-zinc-400">
              start (s)
              <input
                type="number"
                step="0.1"
                value={form.start}
                onChange={(e) => setForm({ ...form, start: Number(e.target.value) })}
                className={fieldCls}
              />
            </label>
            <label className="flex-1 text-xs text-zinc-400">
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
          <p className="text-[11px] text-zinc-500">
            Changing start/end re-snaps to word boundaries and clears this reel's renders.
          </p>
        </div>
      )}

      <div className="mt-2 flex flex-wrap gap-1" dir="ltr">
        {REEL_STAGES.map((s) => (
          <span
            key={s}
            title={s}
            className={`rounded px-1.5 py-0.5 text-[10px] ${
              reel.stages[s] ? "bg-emerald-500/20 text-emerald-300" : "bg-zinc-800 text-zinc-500"
            }`}
          >
            {s}
          </span>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2" dir="ltr">
        {!editing ? (
          <>
            <button onClick={onPlaySpan} className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs text-zinc-200 transition hover:bg-zinc-700">
              ▶ Play span
            </button>
            <button onClick={onProcess} className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs text-zinc-200 transition hover:bg-zinc-700" title="Render this reel">
              ⚙ Process
            </button>
            <button onClick={openEdit} className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs text-zinc-200 transition hover:bg-zinc-700">
              ✎ Edit
            </button>
            {packaged && (
              <button onClick={() => setShowFinished((v) => !v)} className="rounded-lg bg-indigo-600/80 px-2.5 py-1 text-xs text-white transition hover:bg-indigo-500">
                {showFinished ? "Hide reel" : "Preview reel"}
              </button>
            )}
            {packaged && (
              <a
                href={reelMediaUrl(videoId, reel.index)}
                download={reel.output_filename}
                className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs text-zinc-200 transition hover:bg-zinc-700"
              >
                ↓ Download
              </a>
            )}
          </>
        ) : (
          <>
            <button onClick={() => saveEdit.mutate()} disabled={saveEdit.isPending} className="rounded-lg bg-indigo-600 px-2.5 py-1 text-xs text-white transition hover:bg-indigo-500 disabled:opacity-50">
              {saveEdit.isPending ? "Saving…" : "Save"}
            </button>
            <button onClick={() => setEditing(false)} className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs text-zinc-200 transition hover:bg-zinc-700">
              Cancel
            </button>
            <button
              onClick={() => {
                if (confirm(`Delete reel ${reel.index}?`)) del.mutate();
              }}
              className="ml-auto rounded-lg bg-red-600/80 px-2.5 py-1 text-xs text-white transition hover:bg-red-600"
            >
              Delete
            </button>
          </>
        )}
      </div>

      {packaged && showFinished && !editing && (
        <video
          src={reelMediaUrl(videoId, reel.index)}
          controls
          className="mt-3 w-full rounded-lg border border-zinc-800 bg-black"
          style={{ maxHeight: 420 }}
        />
      )}
    </div>
  );
}
