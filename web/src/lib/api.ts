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
  doctor: () => http<Doctor>("/doctor"),
  getConfig: () => http<{ config: Record<string, unknown>; schema: unknown }>("/config"),
};

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
