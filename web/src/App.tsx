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
import { api, isActiveJob } from "./lib/api";
import { Library } from "./components/Library";
import { Doctor } from "./components/Doctor";
import { VideoDetail } from "./components/VideoDetail";
import { ConfigEditor } from "./components/ConfigEditor";
import { Gallery } from "./components/Gallery";
import { SilenceRemover } from "./components/SilenceRemover";
import { Logo } from "./components/Logo";

type Tab = "library" | "gallery" | "silence" | "config" | "health";

const TABS: { id: Tab; label: string; icon: typeof Clapperboard }[] = [
  { id: "library", label: "Library", icon: Clapperboard },
  { id: "gallery", label: "Gallery", icon: MonitorPlay },
  { id: "silence", label: "Silence", icon: MicOff },
  { id: "config", label: "Config", icon: Settings2 },
  { id: "health", label: "Health", icon: Stethoscope },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("library");
  const [openId, setOpenId] = useState<string | null>(null);

  // App-wide awareness of running work — polled so jobs started on any screen
  // surface here. See AgDR-0002.
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.listJobs(), refetchInterval: 3000 });
  const activeJobs = (jobs.data ?? []).filter(isActiveJob);
  const activeVideoIds = new Set(activeJobs.map((j) => j.video_id));

  function openVideo(id: string) {
    setTab("library");
    setOpenId(id);
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <button
            onClick={() => {
              setTab("library");
              setOpenId(null);
            }}
            className="flex items-center gap-2.5 rounded-md focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <Logo className="size-6 text-primary" />
            <span className="font-heading text-[15px] font-semibold tracking-tight">
              Reels <span className="text-primary">Studio</span>
            </span>
          </button>
          <div className="flex items-center gap-3">
            {activeJobs.length > 0 && (
              <button
                onClick={() => openVideo(activeJobs[0].video_id)}
                title="Jump to the running job"
                className="flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary transition hover:bg-primary/15 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
              >
                <Loader2 className="size-3.5 animate-spin" />
                {activeJobs.length} running
              </button>
            )}
            <nav className="flex gap-0.5">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => {
                    setTab(id);
                    if (id !== "library") setOpenId(null);
                  }}
                  className={`relative flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
                    tab === id
                      ? "text-foreground after:absolute after:inset-x-2 after:-bottom-[9px] after:h-0.5 after:rounded-full after:bg-primary"
                      : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
                  }`}
                >
                  <Icon className={`size-4 ${tab === id ? "text-primary" : ""}`} />
                  {label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
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
      </main>
    </div>
  );
}
