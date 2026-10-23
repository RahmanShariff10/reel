# Sprint 01 — Foundations

**Weeks:** 1–2

## Goal
The skeleton of the whole system exists. A video uploaded in the web app creates a job, the worker runs placeholder stages, and progress updates in the database. Shared data models and synthetic test videos are ready, so both devs can work independently from sprint 2.

## Slices in this sprint
- [ ] `slice-01-backend-scaffold` (Dev A) — uv project, package layout, config loader, logging, pytest
- [ ] `slice-02-common-models` (Dev A, Dev B reviews) — Pydantic models for every stage file, job paths, atomic file writes
- [ ] `slice-03-synthetic-fixtures` (Dev B) — ffmpeg generator for test videos with a known ground-truth schedule
- [ ] `slice-04-job-store-worker` (Dev A) — SQLite job/reel store, worker loop, pipeline runner with placeholder stages
- [ ] `slice-05-api-core` (Dev B) — FastAPI app: streamed upload, jobs, file serving with Range support
- [ ] `slice-06-frontend-scaffold` (Dev B) — Next.js app, typed API client, upload page

## Human tasks
- [ ] Both: install Python 3.11, uv, Node 20+, ffmpeg.
- [ ] Both: collect 3–5 full T20 matches from one broadcaster (English commentary), plus each match's official highlights video. Store in `data/raw/` (gitignored). Pick 1–2 for development, 2–3 for testing.
- [ ] Both: download the Cricsheet JSON for those matches into `eval/cricsheet/`.
- [ ] Dev A: watch one match and record whether the score box disappears during replays (and when else it disappears). Note the result here.

## Depends on
Nothing.

## Notes for next time
