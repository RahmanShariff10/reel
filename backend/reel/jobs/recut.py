"""Re-cut a reel in another mode without re-analysing the match (stages 8-9 only)."""

from __future__ import annotations

import typing
from pathlib import Path

from reel.common.logging import get_logger
from reel.common.models import Event, ReelPlan, read_model, write_model
from reel.highlights.select import plan_reel
from reel.render.reel import render_reel

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext

log = get_logger("jobs.recut")


def recut(
    ctx: PipelineContext, mode: str, exclude_event_ids: list[str] | None = None
) -> tuple[ReelPlan, Path]:
    """Select clips from the existing events.json for ``mode`` and render that reel."""
    events = read_model(ctx.paths.events_json, list[Event])
    plan = plan_reel(events, mode, ctx.config, set(exclude_event_ids or []))
    write_model(ctx.paths.reel_plan_path(mode), plan)
    out = render_reel(ctx, mode)
    log.info("Re-cut %s reel for job %s: %d clips", mode, ctx.job_id, len(plan.clips))
    return plan, out
