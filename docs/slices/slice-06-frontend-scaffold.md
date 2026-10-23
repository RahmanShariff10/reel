# Slice 06 — Frontend scaffold and upload page

**Owner:** Dev B · **Sprint:** 01 · **Target week:** 2 · **Depends on:** 05 (can start against the API contract with mocks)

## Module
`frontend`

## What to build
- **Project:** a Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui app in `frontend/`.
- **API client** in `frontend/lib/api.ts`, with TypeScript types mirroring the API contract in ARCHITECTURE.md. The base URL comes from `NEXT_PUBLIC_API_URL`.
- **Layout:** a simple header ("Reel").
- **Upload page** at `/`:
  - a drag-and-drop file picker accepting `.mp4`/`.mkv`, showing name and size;
  - an upload progress bar, using XHR upload progress events and `PUT /api/uploads` directly to FastAPI, not through Next.js;
  - an "or use a file on this computer" path input;
  - after upload, it calls `POST /api/jobs` and navigates to `/jobs/{job_id}` (a placeholder page for now).

## Acceptance criteria
- [ ] `npm run build`, `npm run lint` and `tsc --noEmit` pass.
- [ ] Given a `.mp4` file, when selected, then its name and size are shown and the upload button is enabled.
- [ ] Given a non-video file, when selected, then a message explains only .mp4/.mkv are accepted and nothing is uploaded.
- [ ] Given an upload in progress, then the progress bar shows the percent uploaded.
- [ ] Given a successful upload, then the browser navigates to `/jobs/{job_id}`.
- [ ] Given a local path, when submitted, then a job is created without uploading and the browser navigates to the job page.
- [ ] Given an API error, then a readable message is shown (not raw JSON).

## Mockup / reference
```
┌────────────────────────────────────────────┐
│ Reel                                       │
├────────────────────────────────────────────┤
│   Upload a T20 match                       │
│   ┌──────────────────────────────────────┐ │
│   │  Drop a .mp4 / .mkv file here        │ │
│   │  or click to choose                  │ │
│   └──────────────────────────────────────┘ │
│   match_final.mp4 · 2.8 GB                 │
│   [████████████░░░░░░░░] 61%               │
│                                            │
│   Or use a file on this computer:          │
│   [ /path/to/match.mp4          ] [Start]  │
└────────────────────────────────────────────┘
```

## Out of scope for this slice
Progress page (slice 10), results page (slice 24).

## Human review required?
No.
