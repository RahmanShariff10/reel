"""Highlight rating: deliveries → rated events with reasons (first half of stage 8).

Rules (all values in ``config.highlights``):

- Wicket (incl. overturned, flagged), six (runs +6) and four (runs +4) events get a
  base importance by type.
- Bonuses: crowd excitement (up to ``bonus.excitement_max``), replays
  (``bonus.replay_per`` each, capped at ``bonus.replay_cap``), and the last 3 overs of
  an innings or a close chase (``bonus.late_overs``). Importance is capped at 1.0.
- Without the score signal (switched off or no score box) deliveries with high
  excitement and/or replays become ``moment`` events instead.

Clip times are set provisionally to the delivery and finalised by selection.
"""

from __future__ import annotations

from reel.common.config import ReelConfig
from reel.common.models import ClipBoundary, Delivery, Event, Reason


def _overs(over_ball: str | None) -> float | None:
    try:
        return float(over_ball) if over_ball else None
    except ValueError:
        return None


def _excitement_label(value: float) -> str:
    if value >= 0.7:
        return "crowd excitement high"
    if value >= 0.4:
        return "crowd excitement moderate"
    return "crowd excitement low"


def _runs(score: str | None) -> int | None:
    if not score or "/" not in score:
        return None
    try:
        return int(score.split()[-1].split("/")[0])
    except ValueError:
        return None


def rate(deliveries: list[Delivery], cfg: ReelConfig, use_score: bool = True) -> list[Event]:
    h, signals = cfg.highlights, cfg.signals
    base = h.base_importance
    use_audio = signals.audio
    use_replays = signals.replays

    first_innings = [_runs(d.score_after) for d in deliveries if d.innings == 1]
    target = max((r for r in first_innings if r is not None), default=None)

    events: list[Event] = []
    for d in sorted(deliveries, key=lambda d: d.start_s):
        reasons: list[Reason] = []
        if use_score:
            if d.wicket:
                kind, importance = "wicket", base.wicket
                label = "wicket (overturned on review)" if d.overturned else "wicket"
                reasons.append(Reason(signal="score", value="W", label=label))
            elif d.runs_delta == 6:
                kind, importance = "six", base.six
                reasons.append(Reason(signal="score", value=6, label="score +6"))
            elif d.runs_delta == 4:
                kind, importance = "four", base.four
                reasons.append(Reason(signal="score", value=4, label="score +4"))
            else:
                continue
        else:
            excited = use_audio and d.excitement_max >= h.moment_min_excitement
            replayed = use_replays and d.replay_count > 0
            if not (excited or replayed):
                continue
            kind = "moment"
            level = d.excitement_max if use_audio else 0.5
            importance = base.moment_low + (base.moment_high - base.moment_low) * level

        if use_audio and d.excitement_max > 0:
            importance += h.bonus.excitement_max * d.excitement_max
            reasons.append(
                Reason(
                    signal="audio",
                    value=round(d.excitement_max, 3),
                    label=_excitement_label(d.excitement_max),
                )
            )
        if use_replays and d.replay_count > 0:
            importance += min(h.bonus.replay_per * d.replay_count, h.bonus.replay_cap)
            plural = "replay" if d.replay_count == 1 else "replays"
            reasons.append(
                Reason(signal="replays", value=d.replay_count, label=f"{d.replay_count} {plural}")
            )
        overs = _overs(d.over_ball)
        if overs is not None and overs >= h.late_overs_from:
            runs = _runs(d.score_after)
            close = (
                d.innings == 2
                and target is not None
                and runs is not None
                and target + 1 - runs <= h.close_chase_runs
            )
            importance += h.bonus.late_overs
            reasons.append(
                Reason(
                    signal="match",
                    value=d.over_ball,
                    label="close chase" if close else "last 3 overs",
                )
            )

        if kind == "moment":
            confidence = 0.4 + 0.4 * (d.excitement_max if use_audio else 0.5)
        else:
            confidence = 0.95 if d.over_ball else 0.8
        events.append(
            Event(
                id=f"ev-{len(events) + 1:03d}",
                delivery_id=d.id,
                type=kind,
                innings=d.innings,
                over_ball=d.over_ball,
                score_text=d.score_after,
                importance=round(min(1.0, importance), 4),
                confidence=round(confidence, 3),
                reasons=reasons,
                moment_s=d.t_hit_s if d.t_hit_s is not None else d.start_s,
                clip=ClipBoundary(start_s=d.start_s, end_s=d.end_s),
                overturned=d.overturned,
            )
        )
    return events
