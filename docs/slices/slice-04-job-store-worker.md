# Slice 04 — Job store, worker and pipeline runner

**Owner:** Dev A · **Sprint:** 01 · **Target week:** 2 · **Depends on:** 01, 02

## Module
`jobs`

## What to build
- **SQLite store** at `{data_dir}/reel.db` with `Job` and `Reel` tables as in ARCHITECTURE.md. Functions: `create_job`, `get_job`, `list_jobs`, `claim_next_job` (atomic), `update_progress(job_id, stage, progress)`, `finish_job`, `fail_job(job_id, message)`, and the same set for reels (`create_reel_request`, `claim_next_reel`, …).
- **Pipeline runner:** an ordered list of `Stage` objects, each with a name, the output files it produces, a progress weight and `run(ctx)`. A stage whose outputs are all valid (`is_valid`) is skipped. Progress is the weighted share of finished stages, updated during long stages via a callback.
- **Worker** `python -m reel.jobs.worker`: loops, claims the oldest queued job and runs the pipeline, then claims queued reels (re-cut is wired in slice 22), and sleeps when idle. Supports `--once`. On start, jobs left `running` are put back to `queued`.
- **Placeholder stages** with the 9 real stage names that write minimal valid outputs, so the whole flow works end to end before real stages exist.

## Acceptance criteria
- [ ] Given a new job, when `create_job` is called, then its status is `queued` and progress 0.
- [ ] Given a queued job, when `worker --once` runs, then the job ends `done` with progress 100 and every placeholder stage ran in order.
- [ ] Given a stage whose output files already exist and are valid, when the pipeline runs, then that stage is not invoked.
- [ ] Given a stage that raises, when the pipeline runs, then the job is `failed`, the error message is stored, and later stages do not run.
- [ ] Given two workers claiming at the same time, then no job is claimed twice.
- [ ] Given a job left `running` by a killed worker, when a worker starts, then the job is re-queued and resumes, skipping completed stages.
- [ ] Given a running job, then progress never decreases.
- [ ] Given a (job, mode) pair, then at most one `Reel` row exists.

## Out of scope for this slice
Real stage logic. The HTTP API (slice 05). Re-cut logic (slice 22).

## Human review required?
No.
