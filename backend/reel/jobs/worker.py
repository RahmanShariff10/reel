"""Worker process for Reel background jobs and reels.

Usage::

    python -m reel.jobs.worker [--once] [--interval 1.0] [--data-dir PATH] [--db-path PATH]

Claims queued jobs one at a time, executes pipeline stages, claims queued
reels, and sleeps when idle. Resets stale running jobs on startup.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from reel.common.config import load_config
from reel.common.logging import get_logger, setup_logging
from reel.common.paths import JobPaths
from reel.jobs.pipeline import PipelineContext, run_pipeline
from reel.jobs.placeholders import DUMMY_MP4_BYTES
from reel.jobs.store import (
    claim_next_job,
    claim_next_reel,
    fail_reel,
    finish_reel,
    get_default_db_path,
    get_job,
    init_db,
    requeue_stale_jobs,
)

log = get_logger("jobs.worker")


class Worker:
    """Orchestrates job claiming, pipeline execution, and idle polling."""

    def __init__(
        self,
        db_path: Path | str | None = None,
        data_dir: Path | str | None = None,
        poll_interval_s: float = 1.0,
    ) -> None:
        cfg = load_config()
        self.data_dir = Path(data_dir) if data_dir is not None else Path(cfg.data_dir)
        self.db_path = (
            Path(db_path) if db_path is not None else get_default_db_path(self.data_dir)
        )
        self.poll_interval_s = float(poll_interval_s)
        self._running = False

    def setup(self) -> None:
        """Initialize database schema and requeue any stale running jobs."""
        init_db(self.db_path)
        requeued = requeue_stale_jobs(self.db_path)
        if requeued > 0:
            log.warning("Worker restart: requeued %d stale running job(s)", requeued)

    def process_one_job(self) -> bool:
        """Attempt to claim and process a single queued job.

        Returns True if a job was found and processed; False if no job was queued.
        """
        job = claim_next_job(self.db_path)
        if not job:
            return False

        log.info("Claimed job %s (input: %s)", job.id, job.input_path)
        paths = JobPaths(job.id, data_dir=self.data_dir)
        ctx = PipelineContext(
            job_id=job.id,
            db_path=self.db_path,
            paths=paths,
            input_path=Path(job.input_path),
        )

        try:
            run_pipeline(ctx)
        except Exception as exc:
            log.error("Pipeline execution failed for job %s: %s", job.id, exc)

        return True

    def process_one_reel(self) -> bool:
        """Attempt to claim and process a single queued reel request.

        Returns True if a reel was processed; False if none was queued.
        """
        reel = claim_next_reel(self.db_path)
        if not reel:
            return False

        log.info("Claimed reel request for job %s, mode %s", reel.job_id, reel.mode)
        parent_job = get_job(self.db_path, reel.job_id)
        if not parent_job or parent_job.status != "done":
            msg = f"Cannot generate reel {reel.mode}: parent job {reel.job_id} is not done"
            log.warning(msg)
            fail_reel(self.db_path, reel.job_id, reel.mode, msg)
            return True

        paths = JobPaths(reel.job_id, data_dir=self.data_dir)
        reel_file = paths.reel_path(reel.mode)
        reel_file.parent.mkdir(parents=True, exist_ok=True)
        reel_file.write_bytes(DUMMY_MP4_BYTES)

        finish_reel(
            self.db_path,
            job_id=reel.job_id,
            mode=reel.mode,
            path=str(reel_file),
            duration_s=14.0,
            event_ids=["ev-01"],
        )
        log.info("Finished reel %s for job %s", reel.mode, reel.job_id)
        return True

    def run(self, once: bool = False) -> None:
        """Run the worker loop."""
        self._running = True
        self.setup()
        log.info(
            "Worker started (db: %s, data: %s, once: %s)",
            self.db_path,
            self.data_dir,
            once,
        )

        while self._running:
            # 1. Process all queued jobs first
            if self.process_one_job():
                continue

            # 2. Process all queued reels
            if self.process_one_reel():
                continue

            # 3. If nothing was claimed
            if once:
                log.info("Queue is empty and --once was requested. Exiting.")
                break

            time.sleep(self.poll_interval_s)

    def stop(self) -> None:
        """Signal worker to stop after current iteration."""
        self._running = False


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for python -m reel.jobs.worker."""
    parser = argparse.ArgumentParser(
        description="Reel background worker process",
        prog="python -m reel.jobs.worker",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process current queued items and exit immediately",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds when idle (default: 1.0)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Root data directory (defaults to config data_dir)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="SQLite database path (defaults to {data_dir}/reel.db)",
    )

    args = parser.parse_args(argv)

    setup_logging()
    worker = Worker(
        db_path=args.db_path,
        data_dir=args.data_dir,
        poll_interval_s=args.interval,
    )

    def handle_signal(sig, frame):
        log.info("Received signal %s, stopping worker...", sig)
        worker.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        worker.run(once=args.once)
        return 0
    except Exception as exc:
        log.critical("Worker crashed: %s", exc, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
