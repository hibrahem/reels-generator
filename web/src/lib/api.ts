// Typed client for the Reels Studio API.

export type VideoSummary = {
  id: string;
  filename: string;
  ingested: boolean;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  has_audio: boolean | null;
  completed_stages: string[];
  reel_count: number;
  warning_count: number;
};

export type ReelStage =
  | "plan-layout"
  | "cut"
  | "reframe"
  | "caption"
  | "brand"
  | "package";

export type Reel = {
  index: number;
  start: number;
  end: number;
  duration: number;
  title: string;
  hook: string;
  caption: string;
  reason: string;
  confidence: number;
  visual_dependent: boolean;
  mode: string | null;
  output_filename: string;
  /** mtime of the rendered file — appended to the media URL so re-renders bust the cache. */
  rendered_at: number | null;
  stages: Record<ReelStage, boolean>;
};

export type VideoDetail = {
  id: string;
  filename: string;
  ingested: boolean;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  fps: number | null;
  has_audio: boolean | null;
  transcript_available: boolean;
  completed_stages: string[];
  warnings: string[];
  reels: Reel[];
};

export type TranscriptWord = { text: string; start: number; end: number; probability: number | null };
export type TranscriptSegment = { text: string; start: number; end: number; words: TranscriptWord[] };
export type Transcript = {
  source_id: string;
  language: string;
  duration_seconds: number;
  segments: TranscriptSegment[];
};

export type DoctorCheck = { name: string; ok: boolean; detail: string };
export type Doctor = { checks: DoctorCheck[] };

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listVideos: () => http<VideoSummary[]>("/videos"),
  scanVideos: () => http<VideoSummary[]>("/videos/scan", { method: "POST" }),
  getVideo: (id: string) => http<VideoDetail>(`/videos/${encodeURIComponent(id)}`),
  getTranscript: (id: string) => http<Transcript>(`/videos/${encodeURIComponent(id)}/transcript`),
  // Save word-level transcript edits. Server preserves each word's start/end (only text changes).
  editTranscript: (id: string, segments: TranscriptSegment[]) =>
    http<Transcript>(`/videos/${encodeURIComponent(id)}/transcript`, {
      method: "PATCH",
      body: JSON.stringify({ segments }),
    }),
  doctor: () => http<Doctor>("/doctor"),
  getConfig: () => http<{ config: Record<string, unknown>; schema: unknown }>("/config"),

  runPipeline: (
    id: string,
    body: { from_stage: string; to_stage: string; reel_indices?: number[] },
  ) =>
    http<{ job_id: string }>(`/videos/${encodeURIComponent(id)}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runReel: (id: string, index: number) =>
    http<{ job_id: string }>(`/videos/${encodeURIComponent(id)}/reels/${index}/run`, {
      method: "POST",
    }),
  makePreview: (id: string) =>
    http<{ job_id: string }>(`/videos/${encodeURIComponent(id)}/preview`, { method: "POST" }),
  editReel: (
    id: string,
    index: number,
    edit: Partial<{ start: number; end: number; title: string; hook: string; caption: string }>,
  ) =>
    http<VideoDetail>(`/videos/${encodeURIComponent(id)}/reels/${index}`, {
      method: "PATCH",
      body: JSON.stringify(edit),
    }),
  deleteReel: (id: string, index: number) =>
    http<VideoDetail>(`/videos/${encodeURIComponent(id)}/reels/${index}`, { method: "DELETE" }),
  listJobs: (videoId?: string) =>
    http<JobSummary[]>(`/jobs${videoId ? `?video_id=${encodeURIComponent(videoId)}` : ""}`),
};

export type JobEvent = { stage: string; source_id: string; message: string; ts: number };

export type JobState = "queued" | "running" | "done" | "failed";

export type JobSummary = {
  id: string;
  kind: string;
  video_id: string;
  from_stage: string | null;
  to_stage: string | null;
  reel_indices: number[] | null;
  state: JobState;
  error: string | null;
  events: JobEvent[];
};

// A job is "active" (still doing work) when queued or running.
export const isActiveJob = (j: JobSummary) => j.state === "queued" || j.state === "running";

// Subscribe to a job's live progress via SSE. Returns a cleanup function.
export function subscribeJob(
  jobId: string,
  handlers: {
    onProgress: (e: JobEvent) => void;
    onEnd: (state: string, error: string | null) => void;
  },
): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/events`);
  es.addEventListener("progress", (e) =>
    handlers.onProgress(JSON.parse((e as MessageEvent).data)),
  );
  es.addEventListener("end", (e) => {
    const d = JSON.parse((e as MessageEvent).data);
    handlers.onEnd(d.state, d.error);
    es.close();
  });
  es.onerror = () => es.close();
  return () => es.close();
}

export const mediaUrl = (id: string) => `/api/videos/${encodeURIComponent(id)}/media`;
export const posterUrl = (id: string) => `/api/videos/${encodeURIComponent(id)}/poster`;
export const reelMediaUrl = (id: string, index: number, renderedAt?: number | null) =>
  `/api/videos/${encodeURIComponent(id)}/reels/${index}/media${
    renderedAt != null ? `?v=${renderedAt}` : ""
  }`;

export function fmtClock(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

// --- Silence Remover tool (standalone from the reels pipeline) ---

export type SilenceResult = {
  original_duration: number;
  output_duration: number;
  cuts_removed: number;
  output_filename: string;
};

export type SilenceSettings = {
  threshold_db: number;
  min_silence: number;
  padding: number;
};

export const SILENCE_DEFAULTS: SilenceSettings = {
  threshold_db: -35,
  min_silence: 0.6,
  padding: 0.15,
};

export async function removeSilence(
  file: File,
  settings: SilenceSettings,
): Promise<{ job_id: string; token: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("threshold_db", String(settings.threshold_db));
  form.append("min_silence", String(settings.min_silence));
  form.append("padding", String(settings.padding));
  // No Content-Type header: the browser sets the multipart boundary.
  const res = await fetch("/api/silence/jobs", { method: "POST", body: form });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${await res.text()}`);
  return res.json();
}

export const getSilenceResult = (token: string) =>
  http<SilenceResult>(`/silence/jobs/${encodeURIComponent(token)}/result`);

export const silenceDownloadUrl = (token: string) =>
  `/api/silence/jobs/${encodeURIComponent(token)}/download`;

export const STAGES = [
  "ingest",
  "transcribe",
  "select",
  "plan-layout",
  "cut",
  "reframe",
  "caption",
  "brand",
  "package",
] as const;
