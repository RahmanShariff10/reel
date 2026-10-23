# Slice 22 — Pipeline wiring, re-cut and CLI

**Owner:** Dev A · **Sprint:** 05 · **Target week:** 9–10 · **Depends on:** 07–21

## Module
`jobs`

## What to build
- **Runner:** register all real stages in order (replacing the placeholders), with progress weights roughly matching expected time.
- **Signal switches:** respect `signals.*` in config. A disabled signal's stage writes neutral outputs so later stages still run.
- **Default reel:** after `render`, create the `Reel` row for `5min`.
- **`summary.json`:** per-innings runs / wickets / overs / fours / sixes, `deliveries_found`, `processing_s`, `scorebox_found`, and per-stage timings.
- **Re-cut:** `recut(job_id, mode, exclude_event_ids)` re-runs only the selection and render steps. The worker claims queued `Reel` rows and calls it.
- **CLI:** `uv run reel run <video> [--mode 5min] [--config overrides.yaml] [--job-id ID]` runs the full pipeline without the API or worker (used by the evaluation scripts).

## Acceptance criteria
- [ ] Given the synthetic video, when processed end to end by the worker, then the job is `done`, `reel_5min.mp4` exists, and `events.json` contains the scheduled fours, sixes and wickets.
- [ ] Given the CLI on the synthetic video, then it produces the same `events.json` as the worker.
- [ ] Given a queued reel request for `3min`, then only the selection and render steps run (verified by stage call counts) and the reel row ends `done`.
- [ ] Given `signals.audio: false`, then the audio stage does not run and the job still completes.
- [ ] Given the `--no-scorebox` synthetic video, then the job completes with `moment` events.
- [ ] Given a finished job, then `summary.json` has every field listed in ARCHITECTURE.md.
- [ ] Human check: a full real match completes in ≤ 60 min; record per-stage times in the sprint 05 notes.

## Out of scope for this slice
New API endpoints (slice 23).

## Human review required?
No.
