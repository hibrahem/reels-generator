import { useRef, useState } from "react";
import { Download, Loader2, Scissors } from "lucide-react";
import {
  fmtClock,
  getSilenceResult,
  removeSilence,
  SILENCE_DEFAULTS,
  silenceDownloadUrl,
  subscribeJob,
  type SilenceResult,
  type SilenceSettings,
} from "../lib/api";

type Phase = "idle" | "running" | "done" | "failed";

const FIELDS: {
  key: keyof SilenceSettings;
  label: string;
  hint: string;
  step: number;
}[] = [
  {
    key: "threshold_db",
    label: "Silence threshold (dB)",
    hint: "Audio below this level counts as silence",
    step: 1,
  },
  {
    key: "min_silence",
    label: "Min silence (s)",
    hint: "Shorter quiet gaps are left alone",
    step: 0.1,
  },
  {
    key: "padding",
    label: "Edge padding (s)",
    hint: "Audio kept on each side of a cut",
    step: 0.05,
  },
];

export function SilenceRemover() {
  const [file, setFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<SilenceSettings>(SILENCE_DEFAULTS);
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [result, setResult] = useState<SilenceResult | null>(null);
  const cleanup = useRef<(() => void) | null>(null);

  async function start() {
    if (!file) return;
    setPhase("running");
    setError(null);
    setResult(null);
    setMessage("uploading…");
    try {
      const { job_id, token } = await removeSilence(file, settings);
      setToken(token);
      cleanup.current = subscribeJob(job_id, {
        onProgress: (e) => setMessage(`${e.stage}: ${e.message}`),
        onEnd: async (state, err) => {
          if (state === "done") {
            setResult(await getSilenceResult(token));
            setPhase("done");
          } else {
            setError(err ?? "processing failed");
            setPhase("failed");
          }
        },
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setPhase("failed");
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div>
        <h1 className="font-heading text-xl font-semibold">Silence Remover</h1>
        <p className="text-sm text-muted-foreground">
          Upload a video and get back a copy with the silent passages cut out. Separate from
          the reels pipeline.
        </p>
      </div>

      <label className="block cursor-pointer rounded-xl border-2 border-dashed border-border p-8 text-center transition hover:border-primary/50">
        <input
          type="file"
          accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <span className="text-sm font-medium">{file.name}</span>
        ) : (
          <span className="text-sm text-muted-foreground">Click to choose a video file</span>
        )}
      </label>

      <div className="grid grid-cols-3 gap-4">
        {FIELDS.map((f) => (
          <label key={f.key} className="space-y-1 text-sm" title={f.hint}>
            <span className="text-muted-foreground">{f.label}</span>
            <input
              type="number"
              step={f.step}
              value={settings[f.key]}
              onChange={(e) =>
                setSettings({ ...settings, [f.key]: Number(e.target.value) })
              }
              className="w-full rounded-md border border-border bg-background px-2 py-1.5 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            />
          </label>
        ))}
      </div>

      <button
        onClick={start}
        disabled={!file || phase === "running"}
        className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50"
      >
        {phase === "running" ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Scissors className="size-4" />
        )}
        Remove silence
      </button>

      {phase === "running" && <p className="text-sm text-muted-foreground">{message}</p>}
      {phase === "failed" && error && (
        <p className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </p>
      )}
      {phase === "done" && result && token && (
        <div className="space-y-3 rounded-xl border border-border p-4">
          {result.cuts_removed === 0 ? (
            <p className="text-sm">No silence found — the output equals the input.</p>
          ) : (
            <p className="text-sm">
              Removed <strong>{result.cuts_removed}</strong> silent passage
              {result.cuts_removed === 1 ? "" : "s"}: {fmtClock(result.original_duration)} →{" "}
              {fmtClock(result.output_duration)}
            </p>
          )}
          <a
            href={silenceDownloadUrl(token)}
            download={result.output_filename}
            className="inline-flex items-center gap-2 rounded-lg bg-secondary px-4 py-2 text-sm font-medium text-secondary-foreground transition hover:bg-secondary/80"
          >
            <Download className="size-4" />
            Download {result.output_filename}
          </a>
        </div>
      )}
    </div>
  );
}
