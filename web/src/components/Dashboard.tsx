import { useQueries, useQuery } from "@tanstack/react-query";
import { ArrowRight, Clapperboard, FolderSearch, Loader2 } from "lucide-react";
import { api, fmtClock, isActiveJob, reelMediaUrl, type JobSummary } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "./EmptyState";

/**
 * Home screen: what's happening right now. Running jobs with their latest stage,
 * headline counts, and the most recent finished reels — with jump-offs into the
 * Library and Gallery for the real work.
 */
export function Dashboard({
  onOpenVideo,
  onGoLibrary,
  onGoGallery,
}: {
  onOpenVideo: (id: string) => void;
  onGoLibrary: () => void;
  onGoGallery: () => void;
}) {
  const videos = useQuery({ queryKey: ["videos"], queryFn: api.listVideos });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.listJobs(), refetchInterval: 3000 });
  const activeJobs = (jobs.data ?? []).filter(isActiveJob);

  const ids = (videos.data ?? []).filter((v) => v.reel_count > 0).map((v) => v.id);
  const details = useQueries({
    queries: ids.map((id) => ({ queryKey: ["video", id], queryFn: () => api.getVideo(id) })),
  });
  const finished = details.flatMap((q, i) =>
    (q.data?.reels ?? [])
      .filter((r) => r.stages.package)
      .map((r) => ({ videoId: ids[i], reel: r })),
  );

  const videoCount = videos.data?.length ?? 0;
  const plannedCount = (videos.data ?? []).reduce((n, v) => n + v.reel_count, 0);

  return (
    <div>
      <div className="mb-6">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Home</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {activeJobs.length > 0
            ? `${activeJobs.length} ${activeJobs.length === 1 ? "job" : "jobs"} running`
            : "Nothing running — the studio is idle."}
        </p>
      </div>

      {videos.data && videos.data.length === 0 ? (
        <EmptyState
          icon={FolderSearch}
          action={
            <Button onClick={onGoLibrary}>
              <Clapperboard />
              Open Library
            </Button>
          }
        >
          Drop a source video into the{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">input/</code> folder,
          then scan it from the Library to start making reels.
        </EmptyState>
      ) : (
        <>
          <div className="mb-8 grid grid-cols-3 gap-4">
            <StatCard label="Source videos" value={videoCount} onClick={onGoLibrary} />
            <StatCard label="Reels planned" value={plannedCount} onClick={onGoLibrary} />
            <StatCard label="Reels finished" value={finished.length} onClick={onGoGallery} />
          </div>

          {activeJobs.length > 0 && (
            <section className="mb-8">
              <h3 className="mb-3 font-heading text-xs font-semibold uppercase tracking-wider text-primary">
                Running now
              </h3>
              <div className="flex flex-col gap-2">
                {activeJobs.map((j) => (
                  <JobRow key={j.id} job={j} onOpen={() => onOpenVideo(j.video_id)} />
                ))}
              </div>
            </section>
          )}

          <section>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="font-heading text-xs font-semibold uppercase tracking-wider text-primary">
                Recent reels
              </h3>
              {finished.length > 0 && (
                <button
                  onClick={onGoGallery}
                  className="inline-flex items-center gap-1 rounded-md text-sm text-muted-foreground transition hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  View all
                  <ArrowRight className="size-3.5" />
                </button>
              )}
            </div>
            {finished.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No finished reels yet — open a video and run its pipeline.
              </p>
            ) : (
              <div className="grid grid-cols-3 gap-4 sm:grid-cols-4 lg:grid-cols-6">
                {finished.slice(-6).map(({ videoId, reel }) => (
                  <Card
                    key={`${videoId}-${reel.index}`}
                    role="button"
                    tabIndex={0}
                    onClick={() => onOpenVideo(videoId)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onOpenVideo(videoId);
                      }
                    }}
                    className="cursor-pointer gap-1.5 p-1.5 transition hover:ring-primary/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                  >
                    <video
                      src={reelMediaUrl(videoId, reel.index)}
                      preload="metadata"
                      muted
                      className="aspect-[9/16] w-full rounded-md bg-black"
                    />
                    <div className="px-1 pb-1" dir="auto">
                      <p className="line-clamp-1 text-xs font-medium">{reel.title}</p>
                      <p className="text-[10px] text-muted-foreground" dir="ltr">
                        {fmtClock(reel.start)}–{fmtClock(reel.end)}
                      </p>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function StatCard({
  label,
  value,
  onClick,
}: {
  label: string;
  value: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded-xl border border-border bg-card p-4 text-left transition hover:border-primary/40 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <p className="text-[13px] text-muted-foreground">{label}</p>
      <p className="mt-1 font-heading text-2xl font-semibold text-foreground">{value}</p>
    </button>
  );
}

function JobRow({ job, onOpen }: { job: JobSummary; onOpen: () => void }) {
  const last = job.events.length > 0 ? job.events[job.events.length - 1] : null;
  return (
    <button
      onClick={onOpen}
      className="flex w-full items-center gap-3 rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-left transition hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium text-foreground">{job.video_id}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {last ? `${last.stage} — ${last.message}` : job.state}
        </span>
      </span>
      <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
    </button>
  );
}
