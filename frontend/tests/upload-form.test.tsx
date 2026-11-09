/**
 * Tests for slice-06-frontend-scaffold, one per behavioural acceptance criterion.
 * `npm run build`, `npm run lint` and `npm run typecheck` cover the first criterion.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatSize, UploadForm } from "@/components/upload-form";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

class FakeXhr {
  static last: FakeXhr | null = null;
  method = "";
  url = "";
  sent: unknown = null;
  status = 0;
  responseText = "";
  upload: { onprogress?: (event: Partial<ProgressEvent>) => void } = {};
  onload?: () => void;
  onerror?: () => void;

  constructor() {
    FakeXhr.last = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  send(body: unknown) {
    this.sent = body;
  }

  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = typeof body === "string" ? body : JSON.stringify(body);
    this.onload?.();
  }
}

function video(name = "match_final.mp4", bytes = 3 * 1024 * 1024): File {
  const file = new File(["x"], name, { type: "video/mp4" });
  Object.defineProperty(file, "size", { value: bytes });
  return file;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

function pick(file: File) {
  fireEvent.change(screen.getByTestId("file-input"), { target: { files: [file] } });
}

const uploadButton = () => screen.getByRole("button", { name: /^(Upload|Uploading…)$/ });

describe("UploadForm", () => {
  beforeEach(() => {
    push.mockReset();
    FakeXhr.last = null;
    vi.stubGlobal("XMLHttpRequest", FakeXhr);
    vi.stubGlobal("fetch", vi.fn());
  });

  it("shows the name and size of a selected video and enables upload", () => {
    render(<UploadForm />);
    expect(uploadButton()).toBeDisabled();

    pick(video());

    expect(screen.getByText("match_final.mp4")).toBeInTheDocument();
    expect(screen.getByText(/3\.0 MB/)).toBeInTheDocument();
    expect(uploadButton()).toBeEnabled();
  });

  it("accepts a dropped video", () => {
    render(<UploadForm />);
    fireEvent.drop(screen.getByRole("button", { name: /Drop a/ }), {
      dataTransfer: { files: [video("drop.mkv")] },
    });
    expect(screen.getByText("drop.mkv")).toBeInTheDocument();
  });

  it("explains that only videos are accepted and uploads nothing", () => {
    render(<UploadForm />);

    pick(new File(["x"], "notes.txt"));

    expect(screen.getByRole("alert")).toHaveTextContent("Only .mp4 and .mkv files are accepted.");
    expect(uploadButton()).toBeDisabled();
    fireEvent.click(uploadButton());
    expect(FakeXhr.last).toBeNull();
  });

  it("shows the percent uploaded while uploading, straight to the API", async () => {
    render(<UploadForm />);
    pick(video());
    fireEvent.click(uploadButton());

    await waitFor(() => expect(FakeXhr.last).not.toBeNull());
    expect(FakeXhr.last?.method).toBe("PUT");
    expect(FakeXhr.last?.url).toContain("/api/uploads?filename=match_final.mp4");
    expect(FakeXhr.last?.url).toMatch(/^http/);

    FakeXhr.last?.upload.onprogress?.({ lengthComputable: true, loaded: 61, total: 100 });

    expect(await screen.findByText("61%")).toBeInTheDocument();
  });

  it("creates a job and navigates after a successful upload", async () => {
    vi.mocked(fetch).mockResolvedValue(jsonResponse(201, { job_id: "job-1" }));
    render(<UploadForm />);
    pick(video());
    fireEvent.click(uploadButton());
    await waitFor(() => expect(FakeXhr.last).not.toBeNull());

    FakeXhr.last?.respond(200, { upload_id: "u1", filename: "match_final.mp4", size_bytes: 1 });

    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs/job-1"));
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(String(url)).toContain("/api/jobs");
    expect(init?.body).toBe(JSON.stringify({ upload_id: "u1" }));
  });

  it("creates a job from a local path without uploading", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValue(jsonResponse(201, { job_id: "job-2" }));
    render(<UploadForm />);

    await user.type(screen.getByLabelText(/Or use a file/), "/videos/match.mp4");
    await user.click(screen.getByRole("button", { name: "Start" }));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/jobs/job-2"));
    expect(FakeXhr.last).toBeNull();
    expect(vi.mocked(fetch).mock.calls[0][1]?.body).toBe(
      JSON.stringify({ local_path: "/videos/match.mp4" }),
    );
  });

  it("shows a readable message for an API error, not raw JSON", async () => {
    const user = userEvent.setup();
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse(400, { error: { code: "local_file_not_found", message: "No file found." } }),
    );
    render(<UploadForm />);

    await user.type(screen.getByLabelText(/Or use a file/), "/nope.mp4");
    await user.click(screen.getByRole("button", { name: "Start" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("No file found.");
    expect(alert.textContent).not.toContain("{");
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a readable message when an upload fails or the server is unreachable", async () => {
    render(<UploadForm />);
    pick(video());
    fireEvent.click(uploadButton());
    await waitFor(() => expect(FakeXhr.last).not.toBeNull());

    FakeXhr.last?.respond(500, "<html>boom</html>");
    expect(await screen.findByRole("alert")).toHaveTextContent("Something went wrong");

    fireEvent.click(uploadButton());
    await waitFor(() => expect(FakeXhr.last?.sent).not.toBeNull());
    FakeXhr.last?.onerror?.();
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't reach the Reel server");
  });
});

describe("formatSize", () => {
  it.each([
    [2048, "2.0 KB"],
    [5 * 1024 * 1024, "5.0 MB"],
    [2.8 * 1024 * 1024 * 1024, "2.8 GB"],
  ])("formats %d bytes", (bytes, expected) => {
    expect(formatSize(bytes)).toBe(expected);
  });
});
