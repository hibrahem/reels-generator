import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { VideoCard } from "./VideoCard";

export function Library({ onOpen }: { onOpen: (id: string) => void }) {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["videos"], queryFn: api.listVideos });
  const scan = useMutation({
    mutationFn: api.scanVideos,
    onSuccess: (videos) => qc.setQueryData(["videos"], videos),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100">Library</h2>
        <button
          onClick={() => scan.mutate()}
          disabled={scan.isPending}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
        >
          {scan.isPending ? "Scanning…" : "Scan input folder"}
        </button>
      </div>

      {isLoading && <p className="text-zinc-400">Loading…</p>}
      {error && <p className="text-red-400">Failed to load: {String(error)}</p>}

      {data && data.length === 0 && (
        <div className="rounded-xl border border-dashed border-zinc-700 p-10 text-center text-zinc-400">
          No videos found. Drop a video into the <code className="text-zinc-200">input/</code> folder,
          then click <span className="text-zinc-200">Scan input folder</span>.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data?.map((v) => (
          <VideoCard key={v.id} video={v} onOpen={onOpen} />
        ))}
      </div>
    </div>
  );
}
