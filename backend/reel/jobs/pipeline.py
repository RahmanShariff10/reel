"""Pipeline runner and stage orchestration for Reel.

Runs stages sequentially, skips completed stages whose outputs are valid,
updates progress proportionally based on stage weights, and records failures.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from reel.audio.excitement import is_valid_audio, run_audio
from reel.common.config import ReelConfig, load_config
from reel.common.logging import get_logger
from reel.common.paths import JobPaths
from reel.deliveries.segment import is_valid_deliveries, run_deliveries
from reel.ingest import is_valid_ingest, run_ingest
from reel.ingest.scan import is_valid_scan, run_scan
from reel.jobs.placeholders import (
    is_valid_highlights,
    is_valid_render,
    run_highlights,
    run_render,
)
from reel.jobs.store import fail_job, finish_job, update_progress
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


DEFAULT_STAGES: list[Stage] = [
    Stage(name="ingest", weight=5.0, validator=is_valid_ingest, runner=run_ingest),
    Stage(
        name="locate_scorebox",
        weight=10.0,
        validator=is_valid_locate_scorebox,
        runner=run_locate_scorebox,
    ),
    Stage(name="scan", weight=25.0, validator=is_valid_scan, runner=run_scan),
    Stage(name="read_score", weight=15.0, validator=is_valid_read_score, runner=run_read_score),
    Stage(
        name="classify_shots",
        weight=10.0,
        validator=is_valid_classify_shots,
        runner=run_classify_shots,
    ),
    Stage(name="audio", weight=10.0, validator=is_valid_audio, runner=run_audio),
    Stage(name="deliveries", weight=10.0, validator=is_valid_deliveries, runner=run_deliveries),
    Stage(name="highlights", weight=5.0, validator=is_valid_highlights, runner=run_highlights),
    Stage(name="render", weight=10.0, validator=is_valid_render, runner=run_render),
]


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

    for stage in pipeline_stages:
        stage_weight = stage.weight
        stage_start_pct = (cumulative_weight / total_weight) * 100.0
        stage_end_pct = ((cumulative_weight + stage_weight) / total_weight) * 100.0

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

        try:
            stage.run(ctx, cb)
        except Exception as exc:
            msg = f"Stage '{stage.name}' failed: {exc}"
            log.error(msg, exc_info=True)
            fail_job(ctx.db_path, ctx.job_id, msg)
            raise

        update_progress(ctx.db_path, ctx.job_id, stage.name, stage_end_pct)
        cumulative_weight += stage_weight

    finish_job(ctx.db_path, ctx.job_id)
    log.info("Pipeline completed successfully for job %s", ctx.job_id)
