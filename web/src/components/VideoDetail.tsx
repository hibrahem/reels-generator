import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Eye, Layers, Play } from "lucide-react";
import { api, fmtClock, isActiveJob, mediaUrl, STAGES, type Reel } from "../lib/api";
import { Button } from "@/components/ui/button";
import { ReelCard } from "./ReelCard";
import { ReelDetail } from "./ReelDetail";
import { TranscriptView } from "./TranscriptView";
import { JobProgress } from "./JobProgress";
import { Timeline } from "./Timeline";

export function VideoDetail({ id, onBack }: { id: string; onBack: () => void }) {
  const qc = useQueryClient();
  const videoRef = useRef<HTMLVideoElement>(null);
  const playUntilRef = useRef<number | null>(null); // auto-stop boundary for "Play span"
  const [currentTime, setCurrentTime] = useState(0);
  const [activeReel, setActiveReel] = useState<number | null>(null);
  const [loopSpan, setLoopSpan] = useState(false);
  const [bottomTab, setBottomTab] = useState<"transcript" | "summary">("transcript");
  const [jobId, setJobId] = useState<string | null>(null);
  const [fromStage, setFromStage] = useState("plan-layout");
  const [toStage, setToStage] = useState("package");
  const [selectedReel, setSelectedReel] = useState<number | null>(null);

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
  // Jobs come back newest-first; the first active one is the latest in-flight run.
  const activeJob = jobs.data?.find(isActiveJob);
  // Latch onto a reattached job so its JobProgress card persists through the
  // terminal Done/Failed state — symmetric with the locally-started path, which
  // keeps `jobId` set after completion. Without this, a post-refresh viewer's
  // card would vanish the instant the job left the active set (GH-11).
  const [reattachedJobId, setReattachedJobId] = useState<string | null>(null);
  useEffect(() => {
    if (!jobId && activeJob && activeJob.id !== reattachedJobId) {
      setReattachedJobId(activeJob.id);
    }
  }, [jobId, activeJob, reattachedJobId]);
  // Prefer a locally-started job; otherwise the latched reattached job.
  const shownJobId = jobId ?? reattachedJobId;

  function seekTo(t: number, play = true) {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = t;
    if (play) void v.play();
  }

  function playReel(reel: Reel) {
    setActiveReel(reel.index);
    playUntilRef.current = reel.end; // stop at the reel's end to simulate the finished clip
    seekTo(reel.start);
  }

  function onTimeUpdate(e: React.SyntheticEvent<HTMLVideoElement>) {
    const v = e.currentTarget;
    setCurrentTime(v.currentTime);
    const until = playUntilRef.current;
    if (until != null && v.currentTime >= until) {
      if (loopSpan && activeReel != null) {
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

  // Clear the auto-stop boundary only when the user presses play again after we paused,
  // or starts dragging the native scrubber (mousedown on the controls) — handled via onPlay below.
  function onManualPlay() {
    if (videoRef.current && playUntilRef.current != null) {
      // If playback resumes at/after the boundary, the user wants to keep watching.
      if (videoRef.current.currentTime >= playUntilRef.current - 0.05) {
        playUntilRef.current = null;
        setActiveReel(null);
      }
    }
  }

  async function start(promise: Promise<{ job_id: string }>) {
    const { job_id } = await promise;
    setJobId(job_id);
    void qc.invalidateQueries({ queryKey: ["jobs"] }); // refresh detail reattach + global indicator
  }

  function onJobDone() {
    void qc.invalidateQueries({ queryKey: ["video", id] });
    void qc.invalidateQueries({ queryKey: ["transcript", id] });
    void qc.invalidateQueries({ queryKey: ["videos"] });
    void qc.invalidateQueries({ queryKey: ["jobs", id] });
    void qc.invalidateQueries({ queryKey: ["jobs"] });
  }

  if (detail.isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (detail.error) return <p className="text-destructive">Failed: {String(detail.error)}</p>;
  const d = detail.data!;

  // A reel is selected → show the focused per-reel editor instead of the list.
  const selected = selectedReel != null ? d.reels.find((r) => r.index === selectedReel) : undefined;
  if (selected) {
    return (
      <ReelDetail
        key={selected.index}
        videoId={id}
        reel={selected}
        duration={d.duration_seconds ?? 0}
        segments={transcript.data?.segments}
        onBack={() => setSelectedReel(null)}
      />
    );
  }

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
          {d.width}×{d.height} · {d.fps?.toFixed(0)}fps · {fmtClock(d.duration_seconds ?? 0)} ·{" "}
          {d.reels.length} reels
        </span>
      </div>

      {/* Pipeline controls (job trigger) */}
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3">
        <span className="text-sm font-medium text-muted-foreground">Run</span>
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
        <span className="text-sm text-muted-foreground">→</span>
        <select value={toStage} onChange={(e) => setToStage(e.target.value)} className={selectClass}>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
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
        {/* Player + bottom tabs */}
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
            duration={d.duration_seconds ?? 0}
            currentTime={currentTime}
            activeReel={activeReel}
            onPlayReel={playReel}
            onSeek={(t) => seekTo(t, false)}
          />

          <label className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={loopSpan}
              onChange={(e) => setLoopSpan(e.target.checked)}
              className="accent-primary"
            />
            Loop the played span
          </label>

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
          </div>

          <div className="mt-3">
            {bottomTab === "transcript" &&
              (transcript.data ? (
                <TranscriptView
                  segments={transcript.data.segments}
                  currentTime={currentTime}
                  onSeek={(t) => seekTo(t)}
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
                  <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
                    <p className="mb-1 font-medium text-amber-600 dark:text-amber-300">
                      {d.warnings.length} warnings
                    </p>
                    <ul className="list-inside list-disc text-amber-700/80 dark:text-amber-200/80">
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

        {/* Reels panel */}
        <div className="min-w-0">
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Reels ({d.reels.length})
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
                onOpen={() => setSelectedReel(r.index)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
