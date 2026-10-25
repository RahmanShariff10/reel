"""Pipeline runner and stage orchestration for Reel.

Runs stages sequentially, skips completed stages whose outputs are valid,
updates progress proportionally based on stage weights, and records failures.
"""

from __future__ import annotations

import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from reel.audio.excitement import (
    compute_excitement,
    is_valid_audio,
    run_audio,
    write_excitement_rows,
)
from reel.common.config import ReelConfig, load_config
from reel.common.logging import get_logger
from reel.common.models import Meta, ReelPlan, Summary, is_valid, read_model, write_model
from reel.common.paths import JobPaths
from reel.deliveries.segment import is_valid_deliveries, run_deliveries
from reel.highlights.select import is_valid_highlights, run_highlights
from reel.ingest import is_valid_ingest, run_ingest
from reel.ingest.scan import is_valid_scan, run_scan
from reel.jobs.store import (
    create_reel_request,
    fail_job,
    finish_job,
    finish_reel,
    update_progress,
)
from reel.render.reel import is_valid_render, run_render
from reel.scoreboard import is_valid_locate_scorebox, run_locate_scorebox
from reel.scoreboard.score_stage import is_valid_read_score, run_read_score
from reel.shots.classify import is_valid_classify_shots, run_classify_shots

log = get_logger("jobs.pipeline")


@dataclass
class PipelineContext:
    """Context passed to every pipeline stage during execution."""

    job_id: str
    db_path: Path
    paths: JobPaths
    config: ReelConfig = field(default_factory=load_config)
    input_path: Path | None = None


ProgressCallback = Callable[[float], None]
StageRunner = (
    Callable[[PipelineContext], None] | Callable[[PipelineContext, ProgressCallback], None]
)
StageValidator = Callable[[PipelineContext], bool]


@dataclass
class Stage:
    """A discrete unit of processing in the Reel highlight pipeline."""

    name: str
    weight: float
    validator: StageValidator
    runner: StageRunner
    signal: str | None = None  # config.signals.<name> that can switch this stage off
    neutral: Callable[[PipelineContext], None] | None = None  # outputs when switched off

    def is_valid(self, ctx: PipelineContext) -> bool:
        """Check whether the stage's outputs already exist and are valid."""
        try:
            return self.validator(ctx)
        except Exception as exc:
            log.warning("Validation failed for stage %s: %s", self.name, exc)
            return False

    def run(self, ctx: PipelineContext, progress_cb: ProgressCallback) -> None:
        """Execute the stage runner, passing progress_cb if accepted."""
        sig = inspect.signature(self.runner)
        if len(sig.parameters) >= 2:
            self.runner(ctx, progress_cb)  # type: ignore[call-arg]
        else:
            self.runner(ctx)  # type: ignore[call-arg]


def _neutral_read_score(ctx: PipelineContext) -> None:
    """Score signal off: empty readings, timeline and events."""
    for path in (
        ctx.paths.score_readings_json,
        ctx.paths.score_timeline_json,
        ctx.paths.score_events_json,
    ):
        write_model(path, [])


def _neutral_audio(ctx: PipelineContext) -> None:
    """Audio signal off: zero excitement for every second."""
    meta = read_model(ctx.paths.meta_json, Meta)
    write_excitement_rows(
        ctx.paths.excitement_csv, compute_excitement(None, meta.duration_s, ctx.config.audio)
    )


# Weights roughly follow expected CPU time on a full match.
DEFAULT_STAGES: list[Stage] = [
    Stage("ingest", 4.0, is_valid_ingest, run_ingest),
    Stage("locate_scorebox", 4.0, is_valid_locate_scorebox, run_locate_scorebox),
    Stage("scan", 35.0, is_valid_scan, run_scan),
    Stage(
        "read_score",
        10.0,
        is_valid_read_score,
        run_read_score,
        signal="score",
        neutral=_neutral_read_score,
    ),
    Stage("classify_shots", 8.0, is_valid_classify_shots, run_classify_shots),
    Stage("audio", 25.0, is_valid_audio, run_audio, signal="audio", neutral=_neutral_audio),
    Stage("deliveries", 1.0, is_valid_deliveries, run_deliveries),
    Stage("highlights", 1.0, is_valid_highlights, run_highlights),
    Stage("render", 12.0, is_valid_render, run_render),
]


def _finalise(ctx: PipelineContext, timings: dict[str, float]) -> None:
    """Add processing times to summary.json and record the default 5min reel."""
    paths = ctx.paths
    if is_valid(paths.summary_json, Summary):
        summary = read_model(paths.summary_json, Summary)
        write_model(
            paths.summary_json,
            summary.model_copy(
                update={
                    "processing_s": round(sum(timings.values()), 2),
                    "stage_timings": {k: round(v, 2) for k, v in timings.items()},
                }
            ),
        )
    plan_path, reel = paths.reel_plan_path("5min"), paths.reel_path("5min")
    if reel.is_file() and is_valid(plan_path, ReelPlan):
        plan = read_model(plan_path, ReelPlan)
        create_reel_request(ctx.db_path, ctx.job_id, "5min")
        finish_reel(
            ctx.db_path,
            ctx.job_id,
            "5min",
            path=str(reel),
            duration_s=plan.duration_s,
            event_ids=[c.event_id for c in plan.clips],
        )


def run_pipeline(
    ctx: PipelineContext,
    stages: list[Stage] | None = None,
) -> None:
    """Execute the pipeline stages in order for a given job.

    Skips stages whose valid outputs already exist. If a stage raises an
    exception, the job is marked failed with the error message and subsequent
    stages are aborted.

    Parameters
    ----------
    ctx : PipelineContext
        The job execution context.
    stages : list[Stage] | None, optional
        Custom list of stages. Defaults to DEFAULT_STAGES.
    """
    pipeline_stages = stages if stages is not None else DEFAULT_STAGES
    total_weight = sum(s.weight for s in pipeline_stages)
    if total_weight <= 0:
        total_weight = 1.0

    # Ensure output job directory exists
    ctx.paths.ensure_job_dir()

    log.info("Starting pipeline for job %s with %d stages", ctx.job_id, len(pipeline_stages))
    cumulative_weight = 0.0
    timings: dict[str, float] = {}

    for stage in pipeline_stages:
        stage_weight = stage.weight
        stage_start_pct = (cumulative_weight / total_weight) * 100.0
        stage_end_pct = ((cumulative_weight + stage_weight) / total_weight) * 100.0

        if stage.signal and not getattr(ctx.config.signals, stage.signal):
            log.info(
                "Signal '%s' is off; stage '%s' writes neutral outputs", stage.signal, stage.name
            )
            if stage.neutral:
                stage.neutral(ctx)
            update_progress(ctx.db_path, ctx.job_id, stage.name, stage_end_pct)
            cumulative_weight += stage_weight
            continue

        if stage.is_valid(ctx):
            log.info("Stage '%s' output is valid; skipping execution", stage.name)
            update_progress(ctx.db_path, ctx.job_id, stage.name, stage_end_pct)
            cumulative_weight += stage_weight
            continue

        log.info("Running stage '%s' for job %s", stage.name, ctx.job_id)
        update_progress(ctx.db_path, ctx.job_id, stage.name, stage_start_pct)

        def make_progress_cb(start_p: float, end_p: float) -> ProgressCallback:
            def _cb(fraction: float) -> None:
                clamped = max(0.0, min(1.0, float(fraction)))
                current_p = start_p + clamped * (end_p - start_p)
                update_progress(ctx.db_path, ctx.job_id, stage.name, current_p)

            return _cb

        cb = make_progress_cb(stage_start_pct, stage_end_pct)

        started = time.monotonic()
        try:
            stage.run(ctx, cb)
        except Exception as exc:
            msg = f"Stage '{stage.name}' failed: {exc}"
            log.error(msg, exc_info=True)
            fail_job(ctx.db_path, ctx.job_id, msg)
            raise

        timings[stage.name] = time.monotonic() - started
        update_progress(ctx.db_path, ctx.job_id, stage.name, stage_end_pct)
        cumulative_weight += stage_weight

    _finalise(ctx, timings)
    finish_job(ctx.db_path, ctx.job_id)
    log.info("Pipeline completed successfully for job %s", ctx.job_id)
