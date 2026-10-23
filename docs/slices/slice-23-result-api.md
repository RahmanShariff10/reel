# Slice 23 — Result and reel API

**Owner:** Dev B · **Sprint:** 05 · **Target week:** 9–10 · **Depends on:** 05, 22

## Module
`api`

## What to build
Endpoints from ARCHITECTURE.md, with Pydantic response models matching the contract:
- `GET /api/jobs/{id}/result`: `summary`, `scorebox` (with `preview_url`), `events`, and `reels` (each with `url` under `/api/files/...`).
- `GET /api/jobs/{id}/excitement`: per-second values and one marker per event.
- `POST /api/jobs/{id}/reels`: creates or updates the `Reel` row for the mode as `queued`, with `exclude_event_ids`; the worker re-cuts it.
- `GET /api/jobs/{id}/reels/{mode}`: status, url, duration, exclusions, and `clips` with each event's offset in the reel.

## Acceptance criteria
- [ ] Given a job that isn't done, when `GET /result`, then the response is 409 with code `job_not_ready`.
- [ ] Given a finished synthetic job, then `/result` validates against the contract model and every url returns 200 via `/api/files`.
- [ ] Given a match of duration d, then `/excitement` returns ceil(d) values and one marker per event.
- [ ] Given `POST /reels {mode: "3min"}`, then the response is 202, and `GET /reels/3min` later moves from `queued` to `done` (after the worker runs).
- [ ] Given an invalid mode, then the response is 422; given unknown `exclude_event_ids`, then 400.
- [ ] Given a finished reel, then `clips` offsets match the reel plan.

## Out of scope for this slice
Manual score-box endpoint (slice 28).

## Human review required?
No.
