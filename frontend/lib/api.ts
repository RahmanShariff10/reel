/** API client and types mirroring the API contract in docs/ARCHITECTURE.md. */

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type JobState = "queued" | "running" | "done" | "failed";

export type StageName =
  | "ingest"
  | "locate_scorebox"
  | "scan"
  | "read_score"
  | "classify_shots"
  | "audio"
  | "moments"
  | "commentary"
  | "highlights"
  | "render";

export type ReelMode = "3min" | "5min" | "10min" | "all";

export type EventType = "goal" | "penalty" | "red_card" | "chance" | "yellow_card" | "moment";

export interface UploadResult {
  upload_id: string;
  filename: string;
  size_bytes: number;
}

export interface JobSummary {
  job_id: string;
  filename: string;
  status: JobState;
  created_at: string;
  duration_s: number | null;
}

export interface JobStatus {
  job_id: string;
  status: JobState;
  stage: StageName | null;
  progress: number;
  error?: string;
  created_at: string;
  filename: string;
}

export interface Reason {
  signal: string;
  value: unknown;
  label: string;
}

export interface MatchEvent {
  id: string;
  moment_id: string | null;
  type: EventType;
  half: number | null;
  minute: string | null;
  score_text: string | null;
  importance: number;
  confidence: number;
  reasons: Reason[];
  moment_s: number;
  clip: { start_s: number; end_s: number };
  overturned: boolean;
}

export interface MatchSummary {
  teams: string[] | null;
  final_score: string | null;
  halves: { home_goals: number; away_goals: number }[];
  moments_found: number;
  processing_s: number;
  scorebox_found: boolean;
}

export interface Scorebox {
  found: boolean;
  box: number[] | null;
  clock_box: number[] | null;
  confidence: number;
  sample_reading: string | null;
  preview_url: string | null;
}

export interface Reel {
  mode: ReelMode;
  status: JobState;
  url?: string;
  duration_s?: number;
  exclude_event_ids: string[];
  clips?: { event_id: string; offset_s: number; duration_s: number }[];
}

export interface JobResult {
  summary: MatchSummary;
  scorebox: Scorebox;
  events: MatchEvent[];
  reels: Reel[];
}

export interface Excitement {
  step_s: number;
  values: number[];
  markers: { t: number; type: EventType; event_id: string }[];
}

const NETWORK_MESSAGE = "Couldn't reach the Reel server. Check that it's running and try again.";
const FALLBACK_MESSAGE = "Something went wrong. Please try again.";

/** An API failure with a message that is safe to show to the user. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function apiErrorFrom(status: number, body: string): ApiError {
  try {
    const parsed = JSON.parse(body) as { error?: { code?: string; message?: string } };
    if (parsed.error?.message) {
      return new ApiError(parsed.error.message, parsed.error.code ?? "unknown", status);
    }
  } catch {
    // The body wasn't JSON: fall through to the generic message.
  }
  return new ApiError(FALLBACK_MESSAGE, "unknown", status);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(NETWORK_MESSAGE, "network_error");
  }
  const body = await response.text();
  if (!response.ok) {
    throw apiErrorFrom(response.status, body);
  }
  return JSON.parse(body) as T;
}

/**
 * Upload straight to the API with XHR, because fetch can't report upload progress.
 * Uploads never pass through Next.js.
 */
export function uploadFile(
  file: File,
  onProgress: (percent: number) => void,
): Promise<UploadResult> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", `${API_URL}/api/uploads?filename=${encodeURIComponent(file.name)}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText) as UploadResult);
      } else {
        reject(apiErrorFrom(xhr.status, xhr.responseText));
      }
    };
    xhr.onerror = () => reject(new ApiError(NETWORK_MESSAGE, "network_error"));
    xhr.send(file);
  });
}

export function createJob(
  source: { upload_id: string } | { local_path: string },
): Promise<{ job_id: string }> {
  return request("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(source),
  });
}

export function getJob(jobId: string): Promise<JobStatus> {
  return request(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: "no-store" });
}
