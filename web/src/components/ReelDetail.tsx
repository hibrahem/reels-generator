import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, Eye, Play, Scissors } from "lucide-react";
import {
  api,
  fmtClock,
  mediaUrl,
  reelMediaUrl,
  type Reel,
  type ReelStage,
  type TranscriptSegment,
  type VideoDetail,
} from "../lib/api";
import { Button } from "@/components/ui/button";
import { TrimSlider } from "./TrimSlider";
import { TranscriptView } from "./TranscriptView";
import { ReelPipeline } from "./ReelPipeline";

/**
 * Focused single-reel editor. Shown when a reel is selected in {@link VideoDetail}.
 *
 * Combines three ways to set the cut — drag the trim slider, scrub the player, or click
 * transcript segments — with a per-reel pipeline panel that processes (and redoes individual
 * stages of) only this reel. Start/end edits go through the existing PATCH endpoint, which
 * snaps to word boundaries and clears this reel's downstream renders.
 */
export function ReelDetail({
  videoId,
  reel,
  duration,
  segments,
  onBack,
}: {
  videoId: string;
  reel: Reel;
  duration: number;
  segments: TranscriptSegment[] | undefined;
  onBack: () => void;
}) {
  const qc = useQueryClient();
  const videoRef = useRef<HTMLVideoElement>(null);
  const playUntilRef = useRef<number | null>(null);
  const [currentTime, setCurrentTime] = useState(reel.start);
  const [showFinished, setShowFinished] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({
    start: reel.start,
    end: reel.end,
    title: reel.title,
    hook: reel.hook,
    caption: reel.caption,
  });

  const dirty =
    form.start !== reel.start ||
    form.end !== reel.end ||
    form.title !== reel.title ||
    form.hook !== reel.hook ||
    form.caption !== reel.caption;
  const timesChanged = form.start !== reel.start || form.end !== reel.end;

  // Trim window: a padded zoom around the reel so dragging stays precise inside a long video.
  const total = duration > 0 ? duration : Math.max(form.end + 30, 60);
  const pad = Math.max(15, (reel.end - reel.start) * 0.75);
  const windowStart = Math.max(0, reel.start - pad);
  const windowEnd = Math.min(total, reel.end + pad);

  function seekTo(t: number, play = false) {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = t;
    if (play) void v.play();
  }

  function previewCut() {
    playUntilRef.current = form.end;
    seekTo(form.start, true);
  }

  function onTimeUpdate(e: React.SyntheticEvent<HTMLVideoElement>) {
    const v = e.currentTarget;
    setCurrentTime(v.currentTime);
    const until = playUntilRef.current;
    if (until != null && v.currentTime >= until) {
      v.pause();
      playUntilRef.current = null;
    }
  }

  function seekFromTrack(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    seekTo(ratio * total);
  }

  const onSaved = (updated: VideoDetail) => {
    qc.setQueryData(["video", videoId], updated);
    qc.invalidateQueries({ queryKey: ["videos"] });
  };
  const saveEdit = useMutation({
    mutationFn: () => api.editReel(videoId, reel.index, form),
    onSuccess: onSaved,
  });

  async function start(promise: Promise<{ job_id: string }>) {
    setRunning(true);
    try {
      const { job_id } = await promise;
      setJobId(job_id);
      void qc.invalidateQueries({ queryKey: ["jobs"] });
    } catch {
      setRunning(false);
    }
  }
  function onJobDone() {
    setRunning(false);
    void qc.invalidateQueries({ queryKey: ["video", videoId] });
    void qc.invalidateQueries({ queryKey: ["transcript", videoId] });
    void qc.invalidateQueries({ queryKey: ["videos"] });
    void qc.invalidateQueries({ queryKey: ["jobs", videoId] });
    void qc.invalidateQueries({ queryKey: ["jobs"] });
  }

  const pct = (t: number) => Math.max(0, Math.min(100, (t / total) * 100));
  const fieldCls =
    "w-full rounded-lg border border-input bg-background px-2 py-1 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";
  const packaged = reel.stages.package;

  return (
    <div>
      <button
        onClick={onBack}
        className="mb-3 inline-flex items-center gap-1 rounded-md text-sm text-muted-foreground transition hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <ArrowLeft className="size-4" />
        All reels
      </button>

      <div className="mb-4 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
          {reel.index.toString().padStart(2, "0")}
        </span>
        <h2 className="font-heading text-xl font-semibold tracking-tight" dir="auto">
          {reel.title || `Reel ${reel.index}`}
        </h2>
        <span className="text-sm text-muted-foreground">
          {fmtClock(form.start)}–{fmtClock(form.end)} · {(form.end - form.start).toFixed(1)}s
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        {/* Player + trim + transcript */}
        <div className="min-w-0">
          <div className="overflow-hidden rounded-xl border border-border bg-black">
            <video
              ref={videoRef}
              src={mediaUrl(videoId)}
              controls
              className="aspect-video w-full bg-black"
              onTimeUpdate={onTimeUpdate}
            />
          </div>

          {/* Full-duration overview with the cut shown as a purple band */}
          <div
            onClick={seekFromTrack}
            className="relative mt-3 h-8 w-full cursor-pointer rounded-lg border border-border bg-muted/40"
            title="Click to seek"
          >
            <div
              className="pointer-events-none absolute top-0 h-full rounded-md bg-primary/40"
              style={{ left: `${pct(form.start)}%`, width: `${Math.max(pct(form.end) - pct(form.start), 0.5)}%` }}
            />
            <div
              className="pointer-events-none absolute -top-0.5 h-9 w-0.5 bg-foreground/90"
              style={{ left: `${pct(currentTime)}%` }}
            />
          </div>

          {/* Zoomed dual-handle trim slider */}
          <div className="mt-3 rounded-xl border border-border bg-card p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-muted-foreground">Trim</span>
              <Button size="sm" variant="secondary" onClick={previewCut}>
                <Play />
                Preview cut
              </Button>
            </div>
            <TrimSlider
              windowStart={windowStart}
              windowEnd={windowEnd}
              start={form.start}
              end={form.end}
              onChange={(s, e2) => setForm((f) => ({ ...f, start: s, end: e2 }))}
              onScrub={(t) => seekTo(t)}
            />
            <div className="mt-3 flex gap-2" dir="ltr">
              <label className="flex-1 text-xs text-muted-foreground">
                start (s)
                <input
                  type="number"
                  step="0.1"
                  value={form.start}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      start: Math.max(0, Math.min(Number(e.target.value), f.end - 0.1)),
                    }))
                  }
                  className={fieldCls}
                />
              </label>
              <label className="flex-1 text-xs text-muted-foreground">
                end (s)
                <input
                  type="number"
                  step="0.1"
                  value={form.end}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      end: Math.min(total, Math.max(Number(e.target.value), f.start + 0.1)),
                    }))
                  }
                  className={fieldCls}
                />
              </label>
            </div>
            {timesChanged && (
              <p className="mt-2 text-[11px] text-muted-foreground">
                Saving re-snaps to word boundaries and clears this reel's renders.
              </p>
            )}
          </div>

          {/* Transcript — click "start"/"end" on a segment to set the cut */}
          <div className="mt-4">
            <p className="mb-2 text-sm font-medium text-muted-foreground">
              Transcript {segments ? "— click start / end on a line to set the cut" : ""}
            </p>
            {segments ? (
              <TranscriptView
                segments={segments}
                currentTime={currentTime}
                onSeek={(t) => seekTo(t, true)}
                selStart={form.start}
                selEnd={form.end}
                onSetStart={(t) => setForm((f) => ({ ...f, start: Math.min(t, f.end - 0.1) }))}
                onSetEnd={(t) => setForm((f) => ({ ...f, end: Math.max(t, f.start + 0.1) }))}
              />
            ) : (
              <p className="text-sm text-muted-foreground">
                No transcript yet — run the transcribe stage.
              </p>
            )}
          </div>
        </div>

        {/* Metadata + pipeline */}
        <div className="min-w-0 space-y-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Details
            </h3>
            <div className="space-y-2" dir="ltr">
              <input
                value={form.title}
                dir="auto"
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
                placeholder="title"
                className={fieldCls}
              />
              <input
                value={form.hook}
                dir="auto"
                onChange={(e) => setForm((f) => ({ ...f, hook: e.target.value }))}
                placeholder="hook"
                className={fieldCls}
              />
              <textarea
                value={form.caption}
                dir="auto"
                onChange={(e) => setForm((f) => ({ ...f, caption: e.target.value }))}
                placeholder="caption"
                rows={2}
                className={fieldCls}
              />
            </div>
            <div className="mt-3 flex gap-2">
              <Button
                size="sm"
                onClick={() => saveEdit.mutate()}
                disabled={!dirty || saveEdit.isPending}
              >
                <Scissors />
                {saveEdit.isPending ? "Saving…" : "Save edits"}
              </Button>
              {dirty && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() =>
                    setForm({
                      start: reel.start,
                      end: reel.end,
                      title: reel.title,
                      hook: reel.hook,
                      caption: reel.caption,
                    })
                  }
                >
                  Reset
                </Button>
              )}
            </div>
            {saveEdit.error && (
              <p className="mt-2 text-xs text-destructive">{String(saveEdit.error)}</p>
            )}
          </div>

          <ReelPipeline
            reel={reel}
            jobId={jobId}
            busy={running}
            onProcess={() => start(api.runReel(videoId, reel.index))}
            onRedoStage={(stage: ReelStage) =>
              start(
                api.runPipeline(videoId, {
                  from_stage: stage,
                  to_stage: stage,
                  reel_indices: [reel.index],
                }),
              )
            }
            onJobDone={onJobDone}
          />

          {packaged && (
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="flex gap-2">
                <Button size="sm" onClick={() => setShowFinished((v) => !v)}>
                  <Eye />
                  {showFinished ? "Hide reel" : "Preview reel"}
                </Button>
                <Button asChild size="sm" variant="secondary">
                  <a href={reelMediaUrl(videoId, reel.index)} download={reel.output_filename}>
                    <Download />
                    Download
                  </a>
                </Button>
              </div>
              {showFinished && (
                <video
                  src={reelMediaUrl(videoId, reel.index)}
                  controls
                  className="mt-3 w-full rounded-lg border border-border bg-black"
                  style={{ maxHeight: 480 }}
                />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
