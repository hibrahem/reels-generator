import { useState } from "react";
import { Library } from "./components/Library";
import { Doctor } from "./components/Doctor";

type Tab = "library" | "health";

export default function App() {
  const [tab, setTab] = useState<Tab>("library");
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-200">
      <header className="sticky top-0 z-10 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">🎬</span>
            <span className="font-semibold text-zinc-100">Reels Studio</span>
          </div>
          <nav className="flex gap-1">
            {(["library", "health"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
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
        {tab === "library" && openId && (
          <div>
            <button
              onClick={() => setOpenId(null)}
              className="mb-4 text-sm text-indigo-400 hover:text-indigo-300"
            >
              ← Back to library
            </button>
            <div className="rounded-xl border border-dashed border-zinc-700 p-10 text-center text-zinc-400">
              Detail view for <span className="text-zinc-200">{openId}</span> — player, reels &
              pipeline controls arrive in Slice 2.
            </div>
          </div>
        )}
        {tab === "health" && <Doctor />}
      </main>
    </div>
  );
}
