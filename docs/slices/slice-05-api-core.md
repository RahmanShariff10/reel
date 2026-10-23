# Slice 05 — API core

**Owner:** Dev B · **Sprint:** 01 · **Target week:** 2 · **Depends on:** 02, 04

## Module
`api`

## What to build
FastAPI app `reel.api.main:app`, bound to `REEL_API_HOST:REEL_API_PORT` (default `127.0.0.1:8000`), with CORS for `http://localhost:3000`. Endpoints from ARCHITECTURE.md:
- `PUT /api/uploads?filename=…`: streams the request body to `{data_dir}/uploads/{upload_id}/{filename}` in chunks, never holding the whole file in memory. Only `.mp4` and `.mkv` are accepted.
- `POST /api/jobs` with `{upload_id}` or `{local_path}`.
- `GET /api/jobs` and `GET /api/jobs/{id}`.
- `GET /api/files/{id}/{path}`: serves files from the job folder, supports HTTP `Range`, rejects paths that escape the job folder.

All errors use `{ "error": { "code", "message" } }`.

## Acceptance criteria
- [ ] Given a 200 MB body sent in chunks, when uploaded, then the saved file is byte-identical and the response has `upload_id` and `size_bytes`.
- [ ] Given a `.txt` filename, when uploading, then the response is 415 in the error format.
- [ ] Given a valid `upload_id`, when `POST /api/jobs`, then the response is 201 with `job_id` and the job is `queued` in the database.
- [ ] Given a `local_path` that doesn't exist or isn't mp4/mkv, when `POST /api/jobs`, then the response is 400 with a clear error code.
- [ ] Given an unknown job id, when `GET /api/jobs/{id}`, then the response is 404 in the error format.
- [ ] Given a file in a job folder and `Range: bytes=0-99`, when `GET /api/files/...`, then the response is 206 with 100 bytes and a correct `Content-Range` header.
- [ ] Given a path containing `../`, when `GET /api/files/...`, then the request is rejected and nothing outside the job folder is served.
- [ ] Given a request from origin `http://localhost:3000`, then CORS headers allow it.

## Out of scope for this slice
`/result`, `/excitement`, `/reels`, `/scorebox` endpoints (later slices). Authentication (not needed: localhost only).

## Human review required?
No.
