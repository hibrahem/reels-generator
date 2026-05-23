import { useState } from "react";
import { Library } from "./components/Library";
import { Doctor } from "./components/Doctor";
import { VideoDetail } from "./components/VideoDetail";
import { ConfigEditor } from "./components/ConfigEditor";
import { Gallery } from "./components/Gallery";

type Tab = "library" | "gallery" | "config" | "health";

export default function App() {
  const [tab, setTab] = useState<Tab>("library");
  const [openId, setOpenId] = useState<string | null>(null);

  function openVideo(id: string) {
    setTab("library");
    setOpenId(id);
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200">
      <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <button
            onClick={() => {
              setTab("library");
              setOpenId(null);
            }}
            className="flex items-center gap-2"
          >
            <span className="text-xl">🎬</span>
            <span className="font-semibold text-zinc-100">Reels Studio</span>
          </button>
          <nav className="flex gap-1">
            {(["library", "gallery", "config", "health"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => {
                  setTab(t);
                  if (t !== "library") setOpenId(null);
                }}
                className={`rounded-lg px-3 py-1.5 text-sm capitalize transition ${
                  tab === t ? "bg-zinc-800 text-zinc-100" : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                {t}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {tab === "library" && !openId && <Library onOpen={setOpenId} />}
        {tab === "library" && openId && <VideoDetail id={openId} onBack={() => setOpenId(null)} />}
        {tab === "gallery" && <Gallery onOpen={openVideo} />}
        {tab === "config" && <ConfigEditor />}
        {tab === "health" && <Doctor />}
      </main>
    </div>
  );
}
