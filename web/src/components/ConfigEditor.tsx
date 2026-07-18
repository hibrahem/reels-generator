import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ColorField } from "@/components/ColorField";

/** Color fields are detected generically by name so future settings get the picker for free. */
function isColorField(key: string): boolean {
  return key.endsWith("_color");
}

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
  const base =
    "rounded-lg border border-input bg-background px-2 py-1 text-sm focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none";
  let input;
  if (typeof value === "boolean") {
    input = (
      <input
        type="checkbox"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-primary"
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
      <span className="text-sm text-muted-foreground">{label}</span>
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

  if (isLoading || !cfg) return <p className="text-muted-foreground">Loading config…</p>;
  if (error) return <p className="text-destructive">Failed: {String(error)}</p>;

  const dirty = data?.config != null && JSON.stringify(cfg) !== JSON.stringify(data.config);

  return (
    <div className="max-w-3xl pb-20">
      <div className="mb-4">
        <h2 className="font-heading text-2xl font-semibold tracking-tight">Configuration</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Secrets (API keys) are read from <code className="text-foreground">.env</code> and are
          never shown or edited here.
        </p>
      </div>

      {save.error && (
        <pre className="mb-4 whitespace-pre-wrap rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive">
          {String(save.error)}
        </pre>
      )}

      <div className="space-y-4">
        {Object.entries(cfg).map(([section, fields]) => (
          <details key={section} open className="rounded-xl border border-border bg-card">
            <summary className="cursor-pointer px-4 py-3 font-heading text-xs font-semibold uppercase tracking-wider text-primary">
              {section.replace(/_/g, " ")}
            </summary>
            <div className="divide-y divide-border/70 px-4 pb-3">
              {fields && typeof fields === "object" ? (
                Object.entries(fields).map(([key, value]) => {
                  const onChange = (v: unknown) =>
                    setCfg((prev) => ({
                      ...prev!,
                      [section]: { ...prev![section], [key]: v },
                    }));
                  return isColorField(key) ? (
                    <ColorField
                      key={key}
                      label={key}
                      value={typeof value === "string" ? value : value == null ? null : String(value)}
                      onChange={onChange}
                    />
                  ) : (
                    <Field key={key} label={key} value={value} onChange={onChange} />
                  );
                })
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

      {/* Save bar — slides in only when there are unsaved edits */}
      {(dirty || saved) && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/90 backdrop-blur">
          <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-6 py-3">
            <span className="text-sm text-muted-foreground">
              {saved ? (
                <span className="text-emerald-400">Saved ✓</span>
              ) : (
                "Unsaved changes to config.yaml"
              )}
            </span>
            <div className="flex items-center gap-2">
              {dirty && (
                <Button
                  variant="secondary"
                  onClick={() => setCfg(structuredClone(data!.config))}
                  disabled={save.isPending}
                >
                  Discard
                </Button>
              )}
              {dirty && (
                <Button onClick={() => save.mutate()} disabled={save.isPending}>
                  {save.isPending ? "Saving…" : "Save config.yaml"}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
