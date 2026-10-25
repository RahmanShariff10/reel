"""Command-line entry point.

    uv run reel run <video> [--mode 5min] [--config overrides.yaml] [--job-id ID]

Runs the full pipeline on a video without the API or worker (used by the evaluation
scripts) and prints where the outputs are.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from reel.common.config import load_config
from reel.common.logging import setup_logging
from reel.common.models import Summary, is_valid, read_model
from reel.common.paths import JobPaths
from reel.jobs.pipeline import PipelineContext, run_pipeline
from reel.jobs.recut import recut
from reel.jobs.store import create_job, get_default_db_path, get_job, start_job

MODES = ("3min", "5min", "10min", "all")


def run(
    video: Path, mode: str = "5min", config_file: Path | None = None, job_id: str | None = None
) -> PipelineContext:
    overrides = yaml.safe_load(config_file.read_text()) if config_file else None
    cfg = load_config(overrides=overrides or None)
    data_dir = Path(cfg.data_dir)
    db = get_default_db_path(data_dir)
    existing = get_job(db, job_id) if job_id else None
    job = existing or create_job(db, input_path=str(video.resolve()), source="local", job_id=job_id)
    start_job(db, job.id)
    ctx = PipelineContext(
        job_id=job.id,
        db_path=db,
        paths=JobPaths(job.id, data_dir=data_dir),
        config=cfg,
        input_path=video.resolve(),
    )
    run_pipeline(ctx)
    if mode != "5min":
        recut(ctx, mode)
    return ctx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="reel", description="Reel highlight generator")
    sub = parser.add_subparsers(dest="command", required=True)
    p_run = sub.add_parser("run", help="process a match video into a highlight reel")
    p_run.add_argument("video", type=Path)
    p_run.add_argument("--mode", choices=MODES, default="5min")
    p_run.add_argument("--config", type=Path, default=None, help="YAML file of config overrides")
    p_run.add_argument("--job-id", default=None, help="reuse (resume) or name a job")
    args = parser.parse_args(argv)

    setup_logging()
    if not args.video.is_file():
        print(f"error: {args.video} is not a file", file=sys.stderr)
        return 2
    ctx = run(args.video, args.mode, args.config, args.job_id)
    paths = ctx.paths
    print(f"Job:     {ctx.job_id}")
    print(f"Reel:    {paths.reel_path(args.mode)}")
    print(f"Events:  {paths.events_json}")
    if is_valid(paths.summary_json, Summary):
        s = read_model(paths.summary_json, Summary)
        print(f"Summary: {s.deliveries_found} deliveries, processed in {s.processing_s:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
