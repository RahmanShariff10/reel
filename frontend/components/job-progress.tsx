"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Progress } from "@/components/ui/progress";
import { ApiError, getJob, type JobStatus, type StageName } from "@/lib/api";

export const POLL_MS = 2000;
const NOT_FOUND = "job_not_found";

export const STAGES: { name: StageName; label: string }[] = [
  { name: "ingest", label: "Reading video" },
  { name: "locate_scorebox", label: "Finding the score" },
  { name: "scan", label: "Scanning video" },
  { name: "read_score", label: "Reading the score" },
  { name: "classify_shots", label: "Recognising camera shots" },
  { name: "audio", label: "Analysing crowd audio" },
  { name: "moments", label: "Finding key moments" },
  { name: "commentary", label: "Listening to commentary" },
  { name: "highlights", label: "Picking highlights" },
  { name: "render", label: "Rendering reel" },
];

type StageState = "done" | "current" | "pending";

function stageState(job: JobStatus | null, index: number): StageState {
  if (job?.status === "done") return "done";
  const current = STAGES.findIndex((stage) => stage.name === job?.stage);
  if (current < 0) return "pending";
  if (index < current) return "done";
  return index === current ? "current" : "pending";
}

export function formatElapsed(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const pad = (n: number) => String(n).padStart(2, "0");
  const hours = Math.floor(total / 3600);
  const rest = `${pad(Math.floor((total % 3600) / 60))}:${pad(total % 60)}`;
  return hours > 0 ? `${hours}:${rest}` : rest;
}

const MARKS: Record<StageState, string> = { done: "✓", current: "●", pending: "○" };

export function JobProgress({ jobId }: { jobId: string }) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [reconnecting, setReconnecting] = useState(false);
  const [missing, setMissing] = useState<string | null>(null);
  const [now, setNow] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const next = await getJob(jobId);
        if (cancelled) return;
        setJob(next);
        setReconnecting(false);
        setNow(Date.now());
        if (next.status === "done" || next.status === "failed") return;
      } catch (caught) {
        if (cancelled) return;
        if (caught instanceof ApiError && caught.code === NOT_FOUND) {
          setMissing(caught.message);
          return;
        }
        setReconnecting(true);
      }
      timer = setTimeout(poll, POLL_MS);
    }

    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [jobId]);

  const finished = job?.status === "done" || job?.status === "failed";

  useEffect(() => {
    if (finished) return;
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(clock);
  }, [finished]);

  if (missing) {
    return (
      <div className="flex flex-col gap-4">
        <p role="alert">{missing}</p>
        <BackLink />
      </div>
    );
  }

  const percent = job?.status === "done" ? 100 : Math.round(job?.progress ?? 0);
  const elapsed = job && now !== null ? (now - Date.parse(job.created_at)) / 1000 : 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="truncate text-xl font-semibold">
          {job ? `Processing ${job.filename}` : "Loading…"}
        </h1>
        {!finished && (
          <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
            {formatElapsed(elapsed)} elapsed
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Progress value={percent} className="flex-1" aria-label="Overall progress" />
        <span className="w-12 text-right text-sm tabular-nums">{percent}%</span>
      </div>

      {reconnecting && (
        <p role="status" className="text-sm text-muted-foreground">
          Reconnecting…
        </p>
      )}

      <ol className="flex flex-col gap-1.5">
        {STAGES.map((stage, index) => {
          const state = stageState(job, index);
          return (
            <li
              key={stage.name}
              data-state={state}
              aria-current={state === "current" ? "step" : undefined}
              className={
                state === "pending"
                  ? "text-muted-foreground"
                  : state === "current"
                    ? "font-medium"
                    : undefined
              }
            >
              <span aria-hidden className="mr-2 inline-block w-4 text-center">
                {MARKS[state]}
              </span>
              {stage.label}
            </li>
          );
        })}
      </ol>

      {job?.status === "done" && <p className="font-medium">Your highlights are ready.</p>}

      {job?.status === "failed" && (
        <div className="flex flex-col gap-3">
          <p role="alert" className="text-destructive">
            {job.error ?? "Processing failed."}
          </p>
          <BackLink />
        </div>
      )}
    </div>
  );
}

function BackLink() {
  return (
    <Link href="/" className="text-sm underline">
      Back to upload
    </Link>
  );
}
