"use client";

import { useRouter } from "next/navigation";
import { type ChangeEvent, type DragEvent, type FormEvent, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { createJob, uploadFile } from "@/lib/api";

const NOT_A_VIDEO = "Only .mp4 and .mkv files are accepted.";
const UNKNOWN_ERROR = "Something went wrong. Please try again.";

function isVideo(name: string): boolean {
  return /\.(mp4|mkv)$/i.test(name);
}

export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function UploadForm() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [percent, setPercent] = useState<number | null>(null);
  const [localPath, setLocalPath] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);

  function choose(chosen: File | undefined) {
    if (!chosen) return;
    setPercent(null);
    if (isVideo(chosen.name)) {
      setFile(chosen);
      setError(null);
    } else {
      setFile(null);
      setError(NOT_A_VIDEO);
    }
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  }

  async function run(action: () => Promise<{ job_id: string }>) {
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await action();
      router.push(`/jobs/${job_id}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : UNKNOWN_ERROR);
      setPercent(null);
      setBusy(false);
    }
  }

  function startUpload() {
    if (!file) return;
    setPercent(0);
    void run(async () => {
      const { upload_id } = await uploadFile(file, setPercent);
      return createJob({ upload_id });
    });
  }

  function startLocal(event: FormEvent) {
    event.preventDefault();
    const path = localPath.trim();
    if (path) void run(() => createJob({ local_path: path }));
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Upload a football match</h1>

      <input
        ref={inputRef}
        data-testid="file-input"
        type="file"
        accept=".mp4,.mkv"
        className="hidden"
        onChange={(event: ChangeEvent<HTMLInputElement>) => {
          choose(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`rounded-lg border-2 border-dashed px-6 py-12 text-center text-muted-foreground transition-colors ${
          dragging ? "border-primary bg-muted" : "border-border hover:bg-muted/50"
        }`}
      >
        Drop a .mp4 / .mkv file here
        <br />
        or click to choose
      </button>

      {file && (
        <p className="text-sm">
          <span className="font-medium">{file.name}</span>
          <span className="text-muted-foreground"> · {formatSize(file.size)}</span>
        </p>
      )}

      {percent !== null && (
        <div className="flex items-center gap-3">
          <Progress value={percent} className="flex-1" aria-label="Upload progress" />
          <span className="w-12 text-right text-sm tabular-nums">{percent}%</span>
        </div>
      )}

      <div>
        <Button onClick={startUpload} disabled={!file || busy}>
          {busy && percent !== null ? "Uploading…" : "Upload"}
        </Button>
      </div>

      <form onSubmit={startLocal} className="flex flex-col gap-2 border-t pt-6">
        <label htmlFor="local-path" className="text-sm font-medium">
          Or use a file on this computer:
        </label>
        <div className="flex gap-2">
          <Input
            id="local-path"
            placeholder="/path/to/match.mp4"
            value={localPath}
            onChange={(event) => setLocalPath(event.target.value)}
            disabled={busy}
          />
          <Button type="submit" variant="secondary" disabled={!localPath.trim() || busy}>
            Start
          </Button>
        </div>
      </form>

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
