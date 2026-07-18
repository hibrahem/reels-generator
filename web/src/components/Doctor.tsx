import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { api } from "../lib/api";

export function Doctor() {
  const { data, isLoading, error } = useQuery({ queryKey: ["doctor"], queryFn: api.doctor });

  if (isLoading) return <p className="text-muted-foreground">Checking environment…</p>;
  if (error) return <p className="text-destructive">Failed to load: {String(error)}</p>;

  const failing = data!.checks.filter((c) => !c.ok).length;

  return (
    <div className="max-w-2xl">
      <div className="mb-4">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Environment health</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {failing === 0
            ? "All checks passing — the pipeline is ready to run."
            : `${failing} ${failing === 1 ? "check needs" : "checks need"} attention.`}
        </p>
      </div>
      <div className="overflow-hidden rounded-xl border border-border bg-card">
        {data!.checks.map((c) => (
          <div
            key={c.name}
            className="flex items-center gap-3 border-b border-border px-4 py-3 last:border-0"
          >
            {c.ok ? (
              <CheckCircle2 className="size-4 shrink-0 text-emerald-400" />
            ) : (
              <XCircle className="size-4 shrink-0 text-destructive" />
            )}
            <span className="w-36 shrink-0 font-medium text-foreground">{c.name}</span>
            <span
              className={`truncate text-sm ${c.ok ? "text-muted-foreground" : "text-primary"}`}
              title={c.detail}
            >
              {c.detail}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
