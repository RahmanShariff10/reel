"""Delivery segmentation (pipeline stage 7: ``deliveries``).

- A ``run_up`` shot whose midpoint falls while the score box is visible starts a
  delivery (every ``run_up`` shot counts when no score box was found). Run-up shots
  closer than ``deliveries.max_merge_gap_s`` are merged into one delivery.
- ``t_hit_s`` is the end of the run-up shot; ``end_s`` is the next delivery's start
  (or start + ``last_delivery_s`` for the last one).
- Each score event is assigned to the latest delivery that started before it.
- ``replay_count``: run-up shots with the box hidden between ``t_hit_s`` and ``end_s``.
- ``excitement_max``: highest per-second excitement in ``[start_s, end_s]``.
"""

from __future__ import annotations

import bisect
import typing
from dataclasses import dataclass

from reel.common.config import DeliveriesConfig
from reel.common.logging import get_logger
from reel.common.models import (
    Delivery,
    Meta,
    Scorebox,
    ScoreEvent,
    ScoreReading,
    ScoreTimelineEntry,
    Shot,
    is_valid,
    read_excitement_csv,
    read_model,
    write_model,
)

if typing.TYPE_CHECKING:
    from reel.jobs.pipeline import PipelineContext, ProgressCallback

log = get_logger("deliveries.segment")


class Visibility:
    """Score-box visibility at any time, from the timeline (always visible if empty)."""

    def __init__(self, timeline: list[ScoreTimelineEntry]) -> None:
        self.entries = sorted(timeline, key=lambda e: e.time_s)
        self.times = [e.time_s for e in self.entries]

    def at(self, t: float) -> ScoreTimelineEntry | None:
        if not self.entries:
            return None
        i = bisect.bisect_right(self.times, t) - 1
        if i < 0:
            return self.entries[0]
        if i + 1 < len(self.entries) and self.times[i + 1] - t < t - self.times[i]:
            return self.entries[i + 1]
        return self.entries[i]

    def visible(self, t: float) -> bool:
        e = self.at(t)
        return True if e is None else e.visible


@dataclass
class _RunUp:
    start_s: float
    end_s: float


def _fmt_overs(overs: float | None) -> str | None:
    if overs is None:
        return None
    tenths = round(overs * 10)
    return f"{tenths // 10}.{tenths % 10}"


def segment(
    shots: list[Shot],
    timeline: list[ScoreTimelineEntry],
    events: list[ScoreEvent],
    excitement: list[float],
    duration_s: float,
    cfg: DeliveriesConfig,
    readings: list[ScoreReading] | None = None,
) -> list[Delivery]:
    vis = Visibility(timeline)
    mid = lambda s: (s.start_s + s.end_s) / 2  # noqa: E731
    run_ups = [s for s in shots if s.label == "run_up"]

    starts: list[_RunUp] = []
    for s in run_ups:
        if not vis.visible(mid(s)):
            continue
        if starts and s.start_s - starts[-1].end_s < cfg.max_merge_gap_s:
            starts[-1].end_s = s.end_s
        else:
            starts.append(_RunUp(s.start_s, s.end_s))

    teams = sorted(((r.time_s, r.team) for r in readings or [] if r.team), key=lambda x: x[0])
    team_times = [t for t, _ in teams]

    def team_at(t: float) -> str | None:
        i = bisect.bisect_right(team_times, t) - 1
        return teams[i][1] if i >= 0 else (teams[0][1] if teams else None)

    deliveries: list[Delivery] = []
    for i, ru in enumerate(starts):
        end = starts[i + 1].start_s if i + 1 < len(starts) else ru.start_s + cfg.last_delivery_s
        end = min(end, duration_s)
        deliveries.append(
            Delivery(
                id=f"d{i:04d}",
                start_s=round(ru.start_s, 3),
                t_hit_s=round(ru.end_s, 3),
                end_s=round(max(end, ru.end_s), 3),
            )
        )

    # Assign score events to the latest delivery that started before them
    starts_s = [d.start_s for d in deliveries]
    updates: dict[int, dict] = {}
    for ev in sorted(events, key=lambda e: e.time_s):
        if ev.type not in ("runs", "wicket"):
            continue
        i = bisect.bisect_right(starts_s, ev.time_s) - 1
        if i < 0:
            continue
        u = updates.setdefault(i, {"runs_delta": 0, "wicket": False, "overturned": False})
        if ev.type == "runs":
            u["runs_delta"] += ev.runs_delta
        else:
            u["wicket"] = True
            u["overturned"] = ev.overturned
        u["innings"] = ev.innings
        u["over_ball"] = _fmt_overs(ev.overs)
        if ev.runs is not None and ev.wickets is not None:
            team = team_at(ev.time_s)
            u["score_after"] = f"{team + ' ' if team else ''}{ev.runs}/{ev.wickets}"

    out: list[Delivery] = []
    for i, d in enumerate(deliveries):
        u = updates.get(i, {})
        state = vis.at(max(d.start_s, d.end_s - 0.5))
        replays = sum(
            1 for s in run_ups if d.t_hit_s <= mid(s) < d.end_s and not vis.visible(mid(s))
        )
        window = excitement[int(d.start_s) : int(d.end_s) + 1]
        team = team_at(d.end_s)
        score = f"{team + ' ' if team else ''}{state.runs}/{state.wickets}" if state else None
        out.append(
            d.model_copy(
                update={
                    "innings": u.get("innings", state.innings if state else 1),
                    "over_ball": u.get("over_ball") or (_fmt_overs(state.overs) if state else None),
                    "runs_delta": u.get("runs_delta", 0),
                    "wicket": u.get("wicket", False),
                    "overturned": u.get("overturned", False),
                    "score_after": u.get("score_after") or score,
                    "replay_count": replays,
                    "excitement_max": round(max(window), 4) if window else 0.0,
                }
            )
        )
    return out


def is_valid_deliveries(ctx: PipelineContext) -> bool:
    return is_valid(ctx.paths.deliveries_json, list[Delivery])


def run_deliveries(ctx: PipelineContext, progress_cb: ProgressCallback | None = None) -> None:
    paths = ctx.paths
    meta = read_model(paths.meta_json, Meta)
    scorebox = read_model(paths.scorebox_json, Scorebox)
    use_score = scorebox.found and ctx.config.signals.score
    timeline = read_model(paths.score_timeline_json, list[ScoreTimelineEntry]) if use_score else []
    events = read_model(paths.score_events_json, list[ScoreEvent]) if use_score else []
    readings = read_model(paths.score_readings_json, list[ScoreReading]) if use_score else []
    excitement = read_excitement_csv(paths.excitement_csv) if paths.excitement_csv.is_file() else []
    deliveries = segment(
        read_model(paths.shots_json, list[Shot]),
        timeline,
        events,
        excitement,
        meta.duration_s,
        ctx.config.deliveries,
        readings,
    )
    write_model(paths.deliveries_json, deliveries)
    log.info("Found %d deliveries", len(deliveries))
    if progress_cb:
        progress_cb(1.0)
