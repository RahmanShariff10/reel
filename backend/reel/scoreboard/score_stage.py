"""Pipeline stage 4: ``read_score`` (score crops → readings → timeline and events)."""

from __future__ import annotations

import typing

from reel.common.logging import get_logger
from reel.common.models import (
    ScoreEvent,
    ScoreReading,
    ScoreTimelineEntry,
    is_valid,
    write_model,
)
from reel.scoreboard.read import read_job_crops
from reel.scoreboard.state import build_timeline

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("scoreboard.score_stage")


def is_valid_read_score(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return (
        is_valid(paths.score_readings_json, list[ScoreReading])
        and is_valid(paths.score_timeline_json, list[ScoreTimelineEntry])
        and is_valid(paths.score_events_json, list[ScoreEvent])
    )


def run_read_score(ctx: PipelineContext, progress_cb: ProgressCallback | None = None) -> None:
    readings = read_job_crops(ctx, (lambda f: progress_cb(0.9 * f)) if progress_cb else None)
    timeline, events = build_timeline(readings, ctx.config.scoreboard)
    write_model(ctx.paths.score_timeline_json, timeline)
    write_model(ctx.paths.score_events_json, events)
    log.info("Score timeline: %d readings, %d events", len(timeline), len(events))
    if progress_cb:
        progress_cb(1.0)
