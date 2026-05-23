import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

type Cfg = Record<string, Record<string, unknown>>;

async function putConfig(cfg: Cfg) {
  const res = await fetch("/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config: cfg }),
  });
  if (!res.ok) throw new Error((await res.text()) || `${res.status}`);
  return res.json();
}

function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const base = "rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-sm text-zinc-200";
  let input;
  if (typeof value === "boolean") {
    input = (
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-indigo-500"
      />
    );
  } else if (typeof value === "number") {
    input = (
      <input
        type="number"
        value={value}
        step="any"
        onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        className={`${base} w-40`}
      />
    );
  } else {
    input = (
      <input
        type="text"
        value={value == null ? "" : String(value)}
        placeholder={value == null ? "null" : ""}
        onChange={(e) => onChange(e.target.value === "" ? null : e.target.value)}
        className={`${base} w-64`}
      />
    );
  }
  return (
    <label className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-sm text-zinc-400">{label}</span>
      {input}
    </label>
  );
}

export function ConfigEditor() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["config"],
    queryFn: async () => (await fetch("/api/config")).json() as Promise<{ config: Cfg }>,
  });
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data?.config) setCfg(structuredClone(data.config));
  }, [data]);

  const save = useMutation({
    mutationFn: () => putConfig(cfg!),
    onSuccess: () => {
      setSaved(true);
      void qc.invalidateQueries({ queryKey: ["doctor"] });
      setTimeout(() => setSaved(false), 2500);
    },
  });

  if (isLoading || !cfg) return <p className="text-zinc-400">Loading config…</p>;
  if (error) return <p className="text-red-400">Failed: {String(error)}</p>;

  return (
    <div className="max-w-3xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100">Configuration</h2>
        <div className="flex items-center gap-3">
          {saved && <span className="text-sm text-emerald-400">Saved ✓</span>}
          <button
            onClick={() => save.mutate()}
            disabled={save.isPending}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-50"
          >
            {save.isPending ? "Saving…" : "Save config.yaml"}
          </button>
        </div>
      </div>

      {save.error && (
        <pre className="mb-4 whitespace-pre-wrap rounded-lg border border-red-500/40 bg-red-500/5 p-3 text-xs text-red-300">
          {String(save.error)}
        </pre>
      )}
      <p className="mb-4 text-xs text-zinc-500">
        Secrets (API keys) are read from <code className="text-zinc-300">.env</code> and are never
        shown or edited here.
      </p>

      <div className="space-y-4">
        {Object.entries(cfg).map(([section, fields]) => (
          <details key={section} open className="rounded-xl border border-zinc-800 bg-zinc-900/40">
            <summary className="cursor-pointer px-4 py-2 font-medium capitalize text-zinc-200">
              {section}
            </summary>
            <div className="divide-y divide-zinc-800/70 px-4 pb-3">
              {fields && typeof fields === "object" ? (
                Object.entries(fields).map(([key, value]) => (
                  <Field
                    key={key}
                    label={key}
                    value={value}
                    onChange={(v) =>
                      setCfg((prev) => ({
                        ...prev!,
                        [section]: { ...prev![section], [key]: v },
                      }))
                    }
                  />
                ))
              ) : (
                <Field
                  label={section}
                  value={fields}
                  onChange={(v) => setCfg((prev) => ({ ...prev!, [section]: v as never }))}
                />
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
