/** Tests for slice-10-progress-page, one per acceptance criterion. */
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { formatElapsed, JobProgress, POLL_MS, STAGES } from "@/components/job-progress";
import { ApiError, getJob, type JobStatus } from "@/lib/api";

vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  getJob: vi.fn(),
}));

const CREATED = "2026-11-09T10:00:00.000Z";

function status(overrides: Partial<JobStatus> = {}): JobStatus {
  return {
    job_id: "job-1",
    status: "running",
    stage: "scan",
    progress: 48,
    created_at: CREATED,
    filename: "match_final.mp4",
    ...overrides,
  };
}

async function settle(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function stateOf(label: string): string | null {
  return screen.getByText(label).closest("li")!.getAttribute("data-state");
}

describe("JobProgress", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(CREATED).getTime() + 761_000);
    vi.mocked(getJob).mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("lists all ten stages with their friendly names", async () => {
    vi.mocked(getJob).mockResolvedValue(status());
    render(<JobProgress jobId="job-1" />);
    await settle();
    expect(screen.getAllByRole("listitem").map((li) => li.textContent)).toEqual(
      STAGES.map((stage) => expect.stringContaining(stage.label)),
    );
    expect(STAGES.map((stage) => stage.label)).toEqual([
      "Reading video",
      "Finding the score",
      "Scanning video",
      "Reading the score",
      "Recognising camera shots",
      "Analysing crowd audio",
      "Finding key moments",
      "Listening to commentary",
      "Picking highlights",
      "Rendering reel",
    ]);
  });

  it("updates stage and progress every 2 s without reloading", async () => {
    vi.mocked(getJob).mockResolvedValueOnce(status({ stage: "scan", progress: 20 }));
    render(<JobProgress jobId="job-1" />);
    await settle();
    expect(screen.getByText("20%")).toBeInTheDocument();

    vi.mocked(getJob).mockResolvedValueOnce(status({ stage: "read_score", progress: 55 }));
    await settle(POLL_MS);

    expect(POLL_MS).toBeLessThanOrEqual(2000);
    expect(screen.getByText("55%")).toBeInTheDocument();
    expect(stateOf("Reading the score")).toBe("current");
    expect(getJob).toHaveBeenCalledTimes(2);
  });

  it("marks earlier stages done, the current stage current and later ones pending", async () => {
    vi.mocked(getJob).mockResolvedValue(status({ stage: "scan" }));
    render(<JobProgress jobId="job-1" />);
    await settle();

    expect(stateOf("Reading video")).toBe("done");
    expect(stateOf("Finding the score")).toBe("done");
    expect(stateOf("Scanning video")).toBe("current");
    expect(screen.getByText("Scanning video").closest("li")).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(stateOf("Reading the score")).toBe("pending");
    expect(stateOf("Rendering reel")).toBe("pending");
  });

  it("shows every stage pending while queued", async () => {
    vi.mocked(getJob).mockResolvedValue(status({ status: "queued", stage: null, progress: 0 }));
    render(<JobProgress jobId="job-1" />);
    await settle();
    expect(stateOf("Reading video")).toBe("pending");
  });

  it("shows the elapsed time", async () => {
    vi.mocked(getJob).mockResolvedValue(status());
    render(<JobProgress jobId="job-1" />);
    await settle();
    expect(screen.getByText("12:41 elapsed")).toBeInTheDocument();
  });

  it("stops polling when the job finishes and shows the done state", async () => {
    vi.mocked(getJob).mockResolvedValue(status({ status: "done", stage: "render", progress: 100 }));
    render(<JobProgress jobId="job-1" />);
    await settle();
    await settle(POLL_MS * 5);

    expect(getJob).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Your highlights are ready.")).toBeInTheDocument();
    expect(stateOf("Rendering reel")).toBe("done");
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("shows the error and a link back to upload when the job fails", async () => {
    vi.mocked(getJob).mockResolvedValue(
      status({ status: "failed", stage: "scan", error: "Stage 'scan' failed: corrupt video" }),
    );
    render(<JobProgress jobId="job-1" />);
    await settle();
    await settle(POLL_MS * 3);

    expect(screen.getByRole("alert")).toHaveTextContent("Stage 'scan' failed: corrupt video");
    expect(screen.getByRole("link", { name: "Back to upload" })).toHaveAttribute("href", "/");
    expect(getJob).toHaveBeenCalledTimes(1);
  });

  it("shows the current state when the page is reopened", async () => {
    vi.mocked(getJob).mockResolvedValue(status({ stage: "audio", progress: 70 }));
    const first = render(<JobProgress jobId="job-1" />);
    await settle();
    first.unmount();

    vi.mocked(getJob).mockResolvedValue(status({ stage: "render", progress: 95 }));
    render(<JobProgress jobId="job-1" />);
    await settle();

    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(stateOf("Rendering reel")).toBe("current");
  });

  it("stops polling after unmounting", async () => {
    vi.mocked(getJob).mockResolvedValue(status());
    const view = render(<JobProgress jobId="job-1" />);
    await settle();
    view.unmount();
    await settle(POLL_MS * 3);
    expect(getJob).toHaveBeenCalledTimes(1);
  });

  it("shows Reconnecting and recovers when the API comes back", async () => {
    vi.mocked(getJob).mockResolvedValueOnce(status({ progress: 30 }));
    render(<JobProgress jobId="job-1" />);
    await settle();

    vi.mocked(getJob).mockRejectedValueOnce(new ApiError("unreachable", "network_error"));
    await settle(POLL_MS);
    expect(screen.getByText("Reconnecting…")).toBeInTheDocument();
    expect(screen.getByText("30%")).toBeInTheDocument();

    vi.mocked(getJob).mockResolvedValueOnce(status({ progress: 40 }));
    await settle(POLL_MS);
    expect(screen.queryByText("Reconnecting…")).not.toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("stops and explains when the job doesn't exist", async () => {
    vi.mocked(getJob).mockRejectedValue(new ApiError("No job with id x.", "job_not_found", 404));
    render(<JobProgress jobId="x" />);
    await settle();
    await settle(POLL_MS * 3);

    expect(screen.getByRole("alert")).toHaveTextContent("No job with id x.");
    expect(screen.getByRole("link", { name: "Back to upload" })).toBeInTheDocument();
    expect(getJob).toHaveBeenCalledTimes(1);
  });
});

describe("formatElapsed", () => {
  it.each([
    [0, "00:00"],
    [761, "12:41"],
    [3725, "1:02:05"],
    [-5, "00:00"],
  ])("formats %d seconds", (seconds, expected) => {
    expect(formatElapsed(seconds)).toBe(expected);
  });
});
