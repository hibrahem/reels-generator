import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Clapperboard,
  Loader2,
  MicOff,
  MonitorPlay,
  Settings2,
  Stethoscope,
} from "lucide-react";
import { api, isActiveJob, type JobSummary } from "./lib/api";
import { Library } from "./components/Library";
import { Doctor } from "./components/Doctor";
import { VideoDetail } from "./components/VideoDetail";
import { ConfigEditor } from "./components/ConfigEditor";
import { Gallery } from "./components/Gallery";
import { SilenceRemover } from "./components/SilenceRemover";
import { Logo } from "./components/Logo";

type Tab = "library" | "gallery" | "silence" | "config" | "health";

const MAIN_TABS: { id: Tab; label: string; icon: typeof Clapperboard }[] = [
  { id: "library", label: "Library", icon: Clapperboard },
  { id: "gallery", label: "Gallery", icon: MonitorPlay },
  { id: "silence", label: "Silence", icon: MicOff },
];

const SYSTEM_TABS: { id: Tab; label: string; icon: typeof Clapperboard }[] = [
  { id: "config", label: "Config", icon: Settings2 },
  { id: "health", label: "Health", icon: Stethoscope },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("library");
  const [openId, setOpenId] = useState<string | null>(null);

  // App-wide awareness of running work — polled so jobs started on any screen
  // surface in the sidebar job center. See AgDR-0002.
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.listJobs(), refetchInterval: 3000 });
  const activeJobs = (jobs.data ?? []).filter(isActiveJob);
  const activeVideoIds = new Set(activeJobs.map((j) => j.video_id));

  // Failing environment checks surface as a dot on the Health item.
  const doctor = useQuery({
    queryKey: ["doctor"],
    queryFn: api.doctor,
    refetchInterval: 60_000,
  });
  const healthFailing = (doctor.data?.checks ?? []).some((c) => !c.ok);

  function openVideo(id: string) {
    setTab("library");
    setOpenId(id);
  }

  function NavItem({ id, label, icon: Icon, dot = false }: {
    id: Tab;
    label: string;
    icon: typeof Clapperboard;
    dot?: boolean;
  }) {
    const active = tab === id;
    return (
      <button
        onClick={() => {
          setTab(id);
          if (id !== "library") setOpenId(null);
        }}
        title={label}
        className={`relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
          active
            ? "bg-primary/10 text-foreground"
            : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
        }`}
      >
        {active && (
          <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" />
        )}
        <span className="relative">
          <Icon className={`size-4 shrink-0 ${active ? "text-primary" : ""}`} />
          {dot && (
            <span className="absolute -right-1 -top-1 size-2 rounded-full bg-destructive ring-2 ring-card" />
          )}
        </span>
        <span className="hidden lg:inline">{label}</span>
      </button>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden bg-background text-foreground">
      {/* Studio rail — persistent navigation + job center */}
      <aside className="flex h-full w-16 shrink-0 flex-col border-r border-border bg-card/50 lg:w-56">
        <button
          onClick={() => {
            setTab("library");
            setOpenId(null);
          }}
          className="flex items-center gap-2.5 rounded-md px-4 py-4 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          <Logo className="size-6 shrink-0 text-primary" />
          <span className="hidden font-heading text-[15px] font-semibold tracking-tight lg:inline">
            Reels <span className="text-primary">Studio</span>
          </span>
        </button>

        <nav className="flex flex-col gap-0.5 px-2 pt-2">
          {MAIN_TABS.map((t) => (
            <NavItem key={t.id} {...t} />
          ))}
        </nav>

        {/* Job center — always-visible running work */}
        <div className="mt-6 min-h-0 flex-1 overflow-y-auto px-2">
          <p className="hidden px-3 pb-1.5 font-heading text-[10px] font-semibold uppercase tracking-wider text-muted-foreground lg:block">
            Jobs
          </p>
          {activeJobs.length === 0 ? (
            <p className="hidden px-3 text-xs text-muted-foreground/60 lg:block">Idle</p>
          ) : (
            <div className="flex flex-col gap-1">
              {activeJobs.map((j) => (
                <JobItem key={j.id} job={j} onOpen={() => openVideo(j.video_id)} />
              ))}
            </div>
          )}
        </div>

        <nav className="flex flex-col gap-0.5 border-t border-border px-2 py-2">
          {SYSTEM_TABS.map((t) => (
            <NavItem key={t.id} {...t} dot={t.id === "health" && healthFailing} />
          ))}
        </nav>
      </aside>

      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-6 py-8">
          {tab === "library" && !openId && (
            <Library onOpen={setOpenId} activeVideoIds={activeVideoIds} />
          )}
          {tab === "library" && openId && (
            <VideoDetail key={openId} id={openId} onBack={() => setOpenId(null)} />
          )}
          {tab === "gallery" && <Gallery onOpen={openVideo} />}
          {tab === "silence" && <SilenceRemover />}
          {tab === "config" && <ConfigEditor />}
          {tab === "health" && <Doctor />}
        </div>
      </main>
    </div>
  );
}

/** Sidebar job-center row: spinner, video name, latest stage; click jumps to the video. */
function JobItem({ job, onOpen }: { job: JobSummary; onOpen: () => void }) {
  const lastStage = job.events.length > 0 ? job.events[job.events.length - 1].stage : job.state;
  return (
    <button
      onClick={onOpen}
      title={`${job.video_id} — ${lastStage}. Jump to this video.`}
      className="flex w-full items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-2.5 py-2 text-left transition hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none lg:items-start"
    >
      <Loader2 className="size-3.5 shrink-0 animate-spin text-primary lg:mt-0.5" />
      <span className="hidden min-w-0 flex-col lg:flex">
        <span className="truncate text-xs font-medium text-foreground">{job.video_id}</span>
        <span className="truncate text-[11px] text-muted-foreground">{lastStage}</span>
      </span>
    </button>
  );
}
