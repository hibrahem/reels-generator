import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderSearch, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { Button } from "@/components/ui/button";
import { EmptyState } from "./EmptyState";
import { VideoCard } from "./VideoCard";

export function Library({
  onOpen,
  activeVideoIds,
}: {
  onOpen: (id: string) => void;
  activeVideoIds?: Set<string>;
}) {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["videos"], queryFn: api.listVideos });
  const scan = useMutation({
    mutationFn: api.scanVideos,
    onSuccess: (videos) => qc.setQueryData(["videos"], videos),
  });

  return (
    <div>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h2 className="font-heading text-2xl font-semibold tracking-tight">Library</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {data
              ? `${data.length} source ${data.length === 1 ? "video" : "videos"} in the input folder`
              : "Source videos in the input folder"}
          </p>
        </div>
        <Button onClick={() => scan.mutate()} disabled={scan.isPending}>
          <RefreshCw className={scan.isPending ? "animate-spin" : undefined} />
          {scan.isPending ? "Scanning…" : "Scan input folder"}
        </Button>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-56 animate-pulse rounded-xl bg-muted/50" />
          ))}
        </div>
      )}

      {error && (
        <p className="text-sm text-destructive">Failed to load: {String(error)}</p>
      )}

      {data && data.length === 0 && (
        <EmptyState icon={FolderSearch}>
          No videos found. Drop a video into the{" "}
          <code className="rounded bg-muted px-1.5 py-0.5 text-foreground">input/</code> folder,
          then click <span className="text-foreground">Scan input folder</span>.
        </EmptyState>
      )}

      {data && data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((v) => (
            <VideoCard
              key={v.id}
              video={v}
              onOpen={onOpen}
              processing={activeVideoIds?.has(v.id) ?? false}
            />
          ))}
        </div>
      )}
    </div>
  );
}
