"""Clip boundaries, captions and reel selection (second half of stage 8).

- Clip: start = max(run-up start, t_hit - pre_hit_s); end = t_hit + post_hit (wickets
  get longer); never past the next delivery - gap; capped per type.
- Selection for a mode (3min / 5min / 10min / all): wickets first, then other events by
  importance, while the reel (title card + clips) stays within target + tolerance.
  Overturned wickets and excluded events are never selected. Selected clips play in
  match order, trimmed so they don't overlap.
"""

from __future__ import annotations

import re
import typing

from reel.common.config import ReelConfig
from reel.common.logging import get_logger
from reel.common.models import (
    ClipBoundary,
    Delivery,
    Event,
    ReelClip,
    ReelPlan,
    Scorebox,
    is_valid,
    read_model,
    write_model,
)
from reel.highlights.rating import rate

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("highlights.select")

CAPTION_TYPE = {
    "wicket": "WICKET",
    "six": "SIX",
    "four": "FOUR",
    "near_miss": "BIG MOMENT",
    "moment": "BIG MOMENT",
}
MIN_CLIP_S = 2.0


def mode_target_s(mode: str) -> float | None:
    """Target reel length in seconds (None for ``all``)."""
    if mode == "all":
        return None
    m = re.fullmatch(r"(\d+)min", mode)
    if not m:
        raise ValueError(f"Unknown reel mode: {mode!r}")
    return int(m.group(1)) * 60.0


def clip_for(event: Event, delivery: Delivery, cfg: ReelConfig) -> ClipBoundary:
    c = cfg.highlights.clip
    t_hit = delivery.t_hit_s if delivery.t_hit_s is not None else delivery.start_s
    start = max(delivery.start_s, t_hit - c.pre_hit_s)
    wicket = event.type == "wicket"
    end = t_hit + (c.post_hit_wicket_s if wicket else c.post_hit_boundary_s)
    end = min(end, delivery.end_s - c.gap_before_next_s)
    end = min(end, start + (c.max_wicket_s if wicket else c.max_boundary_s))
    end = max(end, min(start + MIN_CLIP_S, delivery.end_s))
    return ClipBoundary(start_s=round(start, 3), end_s=round(end, 3))


def caption(event: Event) -> str:
    parts = [CAPTION_TYPE[event.type]]
    if event.over_ball:
        parts.append(f"{event.over_ball} ov")
    if event.score_text:
        parts.append(event.score_text)
    return " · ".join(parts)


def add_clips(events: list[Event], deliveries: list[Delivery], cfg: ReelConfig) -> list[Event]:
    by_id = {d.id: d for d in deliveries}
    return [e.model_copy(update={"clip": clip_for(e, by_id[e.delivery_id], cfg)}) for e in events]


def plan_reel(
    events: list[Event], mode: str, cfg: ReelConfig, exclude: set[str] | None = None
) -> ReelPlan:
    exclude = exclude or set()
    target = mode_target_s(mode)
    title = cfg.highlights.title_card_s
    pool = [e for e in events if not e.overturned and e.id not in exclude]

    if target is None:
        chosen = [e for e in pool if e.type in ("wicket", "six", "four", "moment")]
    else:
        budget = target + cfg.highlights.length_tolerance_s - title
        priority = sorted(pool, key=lambda e: (e.type != "wicket", -e.importance, e.moment_s))
        chosen, used = [], 0.0
        for e in priority:
            dur = e.clip.end_s - e.clip.start_s
            if used + dur <= budget:
                chosen.append(e)
                used += dur

    clips: list[ReelClip] = []
    offset = title
    last_end = -1.0
    for e in sorted(chosen, key=lambda e: e.clip.start_s):
        start = max(e.clip.start_s, last_end)
        if e.clip.end_s - start < MIN_CLIP_S:
            continue
        dur = round(e.clip.end_s - start, 3)
        clips.append(
            ReelClip(
                event_id=e.id,
                start_s=round(start, 3),
                end_s=e.clip.end_s,
                duration_s=dur,
                caption=caption(e),
                offset_s=round(offset, 3),
            )
        )
        offset += dur
        last_end = e.clip.end_s
    return ReelPlan(mode=mode, duration_s=round(offset, 3), clips=clips)


def is_valid_highlights(ctx: PipelineContext) -> bool:
    paths = ctx.paths
    return is_valid(paths.events_json, list[Event]) and is_valid(
        paths.reel_plan_path("5min"), ReelPlan
    )


def run_highlights(
    ctx: PipelineContext,
    progress_cb: ProgressCallback | None = None,
    mode: str = "5min",
    exclude: set[str] | None = None,
) -> ReelPlan:
    paths, cfg = ctx.paths, ctx.config
    deliveries = read_model(paths.deliveries_json, list[Delivery])
    scorebox = read_model(paths.scorebox_json, Scorebox)
    events = add_clips(
        rate(deliveries, cfg, use_score=scorebox.found and cfg.signals.score), deliveries, cfg
    )
    write_model(paths.events_json, events)
    plan = plan_reel(events, mode, cfg, exclude)
    write_model(paths.reel_plan_path(mode), plan)
    log.info(
        "%d events; %s reel plan: %d clips, %.0f s",
        len(events),
        mode,
        len(plan.clips),
        plan.duration_s,
    )
    if progress_cb:
        progress_cb(1.0)
    return plan
