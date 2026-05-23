import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";

export function Doctor() {
  const { data, isLoading, error } = useQuery({ queryKey: ["doctor"], queryFn: api.doctor });

  if (isLoading) return <p className="text-zinc-400">Checking environment…</p>;
  if (error) return <p className="text-red-400">Failed to load: {String(error)}</p>;

  return (
    <div className="max-w-2xl">
      <h2 className="mb-4 text-lg font-semibold text-zinc-100">Environment health</h2>
      <div className="overflow-hidden rounded-xl border border-zinc-800">
        {data!.checks.map((c) => (
          <div
            key={c.name}
            className="flex items-center gap-3 border-b border-zinc-800 px-4 py-3 last:border-0"
          >
            <span
              className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${
                c.ok ? "bg-emerald-500" : "bg-red-500"
              }`}
            />
            <span className="w-36 shrink-0 font-medium text-zinc-200">{c.name}</span>
            <span className="truncate text-sm text-zinc-400">{c.detail}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
