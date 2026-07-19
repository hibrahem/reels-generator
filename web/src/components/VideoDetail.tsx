import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, Layers, Play } from "lucide-react";
import {
  api,
  fmtClock,
  isActiveJob,
  mediaUrl,
  STAGES,
  type Reel,
  type ReelStage,
  type VideoDetail as VideoDetailData,
} from "../lib/api";
import { Button } from "@/components/ui/button";
import { ReelCard } from "./ReelCard";
import { ReelInspector, type ReelEditForm } from "./ReelInspector";
import { TranscriptView } from "./TranscriptView";
import { TrimSlider } from "./TrimSlider";
import { JobProgress } from "./JobProgress";
import { Timeline } from "./Timeline";

/**
 * Unified editor workspace for one video. The player, timeline, and transcript are
 * shared surfaces; selecting a reel swaps the right rail from the reel list to the
 * {@link ReelInspector} and puts the shared surfaces into edit mode — the timeline
 * highlights the selected span, a zoomed trim strip appears, and transcript rows gain
 * start/end setters. Esc (or "All reels") deselects. Below lg the inspector opens as
 * an overlay panel so small screens keep a dedicated editing surface.
 */
export function VideoDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const qc = useQueryClient();
  const videoRef = useRef<HTMLVideoElement>(null);
  const playUntilRef = useRef<number | null>(null); // auto-stop boundary for span playback
  const [currentTime, setCurrentTime] = useState(0);
  const [activeReel, setActiveReel] = useState<number | null>(null);
  const [loopSpan, setLoopSpan] = useState(false);
  const [bottomTab, setBottomTab] = useState<"transcript" | "summary">("transcript");
  const [jobId, setJobId] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [fromStage, setFromStage] = useState("plan-layout");
  const [toStage, setToStage] = useState("package");

  // Master-detail: which reel the inspector edits, and the shared edit form the
  // trim strip / transcript / inspector all read and write.
  const [selectedReel, setSelectedReel] = useState<number | null>(null);
  const [form, setForm] = useState<ReelEditForm | null>(null);

  const detail = useQuery({ queryKey: ["video", id], queryFn: () => api.getVideo(id) });
  const transcript = useQuery({
    queryKey: ["transcript", id],
    queryFn: () => api.getTranscript(id),
    retry: false,
  });
  // Reattach to a job already running for this video (survives refresh / re-navigation
  // while the server is up). Poll only while something is active. See AgDR-0002.
  const jobs = useQuery({
    queryKey: ["jobs", id],
    queryFn: () => api.listJobs(id),
    refetchInterval: (q) => (q.state.data?.some(isActiveJob) ? 2000 : false),
  });
  const activeJob = jobs.data?.find(isActiveJob);
  // Latch onto a reattached job so its JobProgress card persists through the
  // terminal Done/Failed state — symmetric with the locally-started path (GH-11).
  const [reattachedJobId, setReattachedJobId] = useState<string | null>(null);
  useEffect(() => {
    if (!jobId && activeJob && activeJob.id !== reattachedJobId) {
      setReattachedJobId(activeJob.id);
    }
  }, [jobId, activeJob, reattachedJobId]);
  const shownJobId = jobId ?? reattachedJobId;

  const selected =
    selectedReel != null ? detail.data?.reels.find((r) => r.index === selectedReel) : undefined;

  function seedForm(r: Reel) {
    setForm({ start: r.start, end: r.end, title: r.title, hook: r.hook, caption: r.caption });
  }

  function select(r: Reel, seekToStart = true) {
    setSelectedReel(r.index);
    seedForm(r);
    if (seekToStart) seekTo(r.start, false);
  }

  function deselect() {
    setSelectedReel(null);
    setForm(null);
  }

  // Esc backs out of the inspector (unless typing in a field, where Esc means "blur").
  useEffect(() => {
    if (selectedReel == null) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const t = e.target as HTMLElement | null;
      if (t instanceof HTMLInputElement || t instanceof HTMLTextAreaElement) return;
      deselect();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedReel]);

  function seekTo(t: number, play = true) {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = t;
    if (play) void v.play();
  }

  function playSpan(start: number, end: number, reelIndex: number | null) {
    setActiveReel(reelIndex);
    playUntilRef.current = end;
    seekTo(start);
  }

  function onTimeUpdate(e: React.SyntheticEvent<HTMLVideoElement>) {
    const v = e.currentTarget;
    setCurrentTime(v.currentTime);
    const until = playUntilRef.current;
    if (until != null && v.currentTime >= until) {
      if (loopSpan && activeReel != null && selectedReel == null) {
        const reel = detail.data?.reels.find((r) => r.index === activeReel);
        if (reel) {
          v.currentTime = reel.start; // restart the span
          return;
        }
      }
      v.pause();
      playUntilRef.current = null;
    }
  }

  // Clear the auto-stop boundary when the user resumes playback past it.
  function onManualPlay() {
    if (videoRef.current && playUntilRef.current != null) {
      if (videoRef.current.currentTime >= playUntilRef.current - 0.05) {
        playUntilRef.current = null;
        setActiveReel(null);
      }
    }
  }

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
    void qc.invalidateQueries({ queryKey: ["video", id] });
    void qc.invalidateQueries({ queryKey: ["transcript", id] });
    void qc.invalidateQueries({ queryKey: ["videos"] });
    void qc.invalidateQueries({ queryKey: ["jobs", id] });
    void qc.invalidateQueries({ queryKey: ["jobs"] });
  }

  const onSaved = (updated: VideoDetailData) => {
    qc.setQueryData(["video", id], updated);
    void qc.invalidateQueries({ queryKey: ["videos"] });
  };
  const saveEdit = useMutation({
    mutationFn: () => api.editReel(id, selectedReel!, form!),
    onSuccess: (updated: VideoDetailData) => {
      onSaved(updated);
      // Re-seed from the saved reel so the form reflects word-boundary snapping.
      const r = updated.reels.find((x) => x.index === selectedReel);
      if (r) seedForm(r);
    },
  });
  const del = useMutation({
    mutationFn: () => api.deleteReel(id, selectedReel!),
    onSuccess: (updated: VideoDetailData) => {
      onSaved(updated);
      deselect(); // the reel is gone — back to the list
    },
  });

  if (detail.isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (detail.error) return <p className="text-destructive">Failed: {String(detail.error)}</p>;
  const d = detail.data!;

  const editing = selected != null && form != null;
  const total = d.duration_seconds ?? 0;
  const dirty =
    editing &&
    (form.start !== selected.start ||
      form.end !== selected.end ||
      form.title !== selected.title ||
      form.hook !== selected.hook ||
      form.caption !== selected.caption);
  const timesChanged =
    editing && (form.start !== selected.start || form.end !== selected.end);

  // Trim window: a padded zoom around the reel so dragging stays precise inside a long video.
  const pad = editing ? Math.max(15, (selected.end - selected.start) * 0.75) : 0;
  const windowStart = editing ? Math.max(0, selected.start - pad) : 0;
  const windowEnd = editing ? Math.min(total || selected.end + 30, selected.end + pad) : 0;

  const fieldCls =
    "w-full rounded-lg border border-input bg-background px-2 py-1 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";
  const selectClass =
    "h-8 rounded-lg border border-input bg-background px-2 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";

  return (
    <div>
      <button
        onClick={onBack}
        className="mb-3 inline-flex items-center gap-1 rounded-md text-sm text-muted-foreground transition hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
      >
        <ArrowLeft className="size-4" />
        Library
      </button>
      <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 className="font-heading text-xl font-semibold tracking-tight">{d.filename}</h2>
        <span className="text-sm text-muted-foreground">
          {d.width}×{d.height} · {d.fps?.toFixed(0)}fps · {fmtClock(total)} · {d.reels.length}{" "}
          reels
        </span>
      </div>

      {/* Pipeline controls (job trigger) */}
      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card p-3">
        <span className="font-heading text-xs font-semibold uppercase tracking-wider text-primary">
          Pipeline
        </span>
        <div className="flex items-center gap-2">
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
        </div>
        <Button
          onClick={() => start(api.runPipeline(id, { from_stage: fromStage, to_stage: toStage }))}
        >
          <Play />
          Run
        </Button>
        <div className="mx-1 h-5 w-px bg-border" />
        <Button
          variant="secondary"
          onClick={() =>
            start(api.runPipeline(id, { from_stage: "plan-layout", to_stage: "package" }))
          }
        >
          <Layers />
          Process all reels
        </Button>
        <Button
          variant="secondary"
          onClick={() => start(api.makePreview(id))}
          title="Transcode a browser-friendly preview (audio in Chrome)"
        >
          <Eye />
          Generate preview
        </Button>
      </div>

      {shownJobId && (
        <div className="mb-4">
          <JobProgress key={shownJobId} jobId={shownJobId} onDone={onJobDone} />
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        {/* Shared surfaces: player + timeline (+ trim strip while editing) + transcript */}
        <div className="min-w-0">
          <div className="overflow-hidden rounded-xl border border-border bg-black">
            <video
              ref={videoRef}
              src={mediaUrl(id)}
              controls
              className="aspect-video w-full bg-black"
              onTimeUpdate={onTimeUpdate}
              onPlay={onManualPlay}
            />
          </div>

          <Timeline
            reels={d.reels}
            duration={total}
            currentTime={currentTime}
            activeReel={activeReel}
            selectedReel={selectedReel}
            onBlockClick={(r) => {
              if (selectedReel == null) playSpan(r.start, r.end, r.index);
              else select(r);
            }}
            onSeek={(t) => seekTo(t, false)}
          />

          {!editing && (
            <label className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={loopSpan}
                onChange={(e) => setLoopSpan(e.target.checked)}
                className="accent-primary"
              />
              Loop the played span
            </label>
          )}

          {/* Zoomed trim strip — only while a reel is being edited */}
          {editing && (
            <div className="mt-3 rounded-xl border border-primary/40 bg-card p-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="font-heading text-xs font-semibold uppercase tracking-wider text-primary">
                  Trim — reel {selected.index.toString().padStart(2, "0")}
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => playSpan(form.start, form.end, null)}
                >
                  <Play />
                  Preview cut
                </Button>
              </div>
              <TrimSlider
                windowStart={windowStart}
                windowEnd={windowEnd}
                start={form.start}
                end={form.end}
                onChange={(s, e2) => setForm((f) => f && { ...f, start: s, end: e2 })}
                onScrub={(t) => seekTo(t, false)}
              />
              <div className="mt-3 flex gap-2" dir="ltr">
                <label className="flex-1 text-xs text-muted-foreground">
                  start (s)
                  <input
                    type="number"
                    step="0.1"
                    value={form.start}
                    onChange={(e) =>
                      setForm(
                        (f) =>
                          f && {
                            ...f,
                            start: Math.max(0, Math.min(Number(e.target.value), f.end - 0.1)),
                          },
                      )
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
                      setForm(
                        (f) =>
                          f && {
                            ...f,
                            end: Math.min(
                              total || Number.MAX_SAFE_INTEGER,
                              Math.max(Number(e.target.value), f.start + 0.1),
                            ),
                          },
                      )
                    }
                    className={fieldCls}
                  />
                </label>
              </div>
            </div>
          )}

          <div className="mt-4 flex gap-1">
            {(["transcript", "summary"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setBottomTab(t)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium capitalize transition ${
                  bottomTab === t
                    ? "bg-secondary text-secondary-foreground"
                    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                }`}
              >
                {t}
              </button>
            ))}
            {editing && bottomTab === "transcript" && (
              <span className="ml-2 self-center text-[11px] text-muted-foreground">
                click start / end on a line to set the cut
              </span>
            )}
          </div>

          <div className="mt-3">
            {bottomTab === "transcript" &&
              (transcript.data ? (
                <TranscriptView
                  segments={transcript.data.segments}
                  currentTime={currentTime}
                  onSeek={(t) => seekTo(t)}
                  selStart={editing ? form.start : undefined}
                  selEnd={editing ? form.end : undefined}
                  onSetStart={
                    editing
                      ? (t) => setForm((f) => f && { ...f, start: Math.min(t, f.end - 0.1) })
                      : undefined
                  }
                  onSetEnd={
                    editing
                      ? (t) => setForm((f) => f && { ...f, end: Math.max(t, f.start + 0.1) })
                      : undefined
                  }
                  videoId={id}
                />
              ) : (
                <p className="text-sm text-muted-foreground">
                  No transcript yet — run the transcribe stage.
                </p>
              ))}
            {bottomTab === "summary" && (
              <div className="space-y-2 text-sm text-foreground">
                <p>Stages done: {d.completed_stages.join(", ") || "—"}</p>
                {d.warnings.length > 0 && (
                  <div className="rounded-lg border border-primary/30 bg-primary/5 p-3">
                    <p className="mb-1 font-medium text-primary">{d.warnings.length} warnings</p>
                    <ul className="list-inside list-disc text-muted-foreground">
                      {d.warnings.slice(0, 12).map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Master-detail rail: reel list, or the inspector for the selected reel.
            Below lg the inspector opens as an overlay panel instead. */}
        <div className="min-w-0">
          {editing ? (
            <div className="fixed inset-y-0 right-0 z-30 w-full max-w-sm overflow-y-auto border-l border-border bg-background p-4 shadow-xl lg:static lg:z-auto lg:w-auto lg:max-w-none lg:overflow-visible lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none">
              <ReelInspector
                key={selected.index}
                videoId={id}
                reel={selected}
                form={form}
                onFormChange={(patch) => setForm((f) => f && { ...f, ...patch })}
                dirty={!!dirty}
                timesChanged={!!timesChanged}
                saving={saveEdit.isPending}
                saveError={saveEdit.error}
                deleting={del.isPending}
                busy={running}
                onSave={() => saveEdit.mutate()}
                onReset={() => seedForm(selected)}
                onDelete={() => {
                  if (confirm(`Delete reel ${selected.index}?`)) del.mutate();
                }}
                onProcess={() => start(api.runReel(id, selected.index))}
                onRedoStage={(stage: ReelStage, cascade: boolean) =>
                  start(
                    api.runPipeline(id, {
                      from_stage: stage,
                      to_stage: cascade ? "package" : stage,
                      reel_indices: [selected.index],
                    }),
                  )
                }
                onClose={deselect}
              />
            </div>
          ) : (
            <>
              <h3 className="mb-3 font-heading text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Reels <span className="text-primary">({d.reels.length})</span>
              </h3>
              <div className="flex flex-col gap-3">
                {d.reels.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No reels selected yet — run the select stage.
                  </p>
                )}
                {d.reels.map((r) => (
                  <ReelCard
                    key={r.index}
                    videoId={id}
                    reel={r}
                    active={activeReel === r.index}
                    onOpen={() => select(r)}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
