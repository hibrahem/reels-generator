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
};

export type JobEvent = { stage: string; source_id: string; message: string; ts: number };

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
export const reelMediaUrl = (id: string, index: number) =>
  `/api/videos/${encodeURIComponent(id)}/reels/${index}/media`;

export function fmtClock(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

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
