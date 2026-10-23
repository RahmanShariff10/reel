# ADR-003 — File-based pipeline stages, SQLite job queue, separate worker process

## Context
Processing a match takes 25–45 min on a CPU. The team is two people working on different stages in parallel, and the evaluation needs to switch signals on and off and re-run parts of the pipeline.

## Decision
- Each pipeline stage writes its output to a file in `data/jobs/<id>/` using a Pydantic model from `common`. A stage is skipped if its valid output already exists.
- Jobs are rows in SQLite. A separate worker process (`python -m reel.jobs.worker`) claims one queued job at a time and runs the pipeline; the FastAPI server only creates jobs, reports status and serves files.

## Why
- **Parallel development:** a stage can be built and tested against saved files from earlier stages.
- **Resume and re-cut:** a crash resumes from the last finished stage; changing reel length re-runs only stages 8–9.
- **Robustness:** restarting or hot-reloading the API during development never kills a long job.
- **Simplicity:** no Redis, Celery or message broker for a single-user, one-job-at-a-time local app.

## Alternatives considered
- **FastAPI `BackgroundTasks`:** fewer moving parts, but jobs die with every server reload.
- **Celery + Redis:** built for multi-worker scale we don't need; extra infrastructure to install and explain.
