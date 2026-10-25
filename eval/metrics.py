"""E2 (delivery detection), E3 (clip accuracy) and runtime metrics."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from reel.common.models import Delivery, Event, Summary

from eval.annotations import Annotation
from eval.cricsheet import Ball

POST_MOMENT_S = 3.0  # a clip must run at least this long after the moment
START_TOLERANCE_S = 0.0  # a clip may start at most this late after the run-up starts
MATCH_WINDOW_S = 20.0  # fallback: event moment within this of the annotated moment


def _legal(over_ball: str | None) -> int | None:
    if not over_ball:
        return None
    try:
        over, ball = over_ball.split(".")
        return int(over) * 6 + int(ball)
    except ValueError:
        return None


@dataclass
class E2:
    detected: int
    truth: int
    matched: int

    @property
    def recall(self) -> float:
        return self.matched / self.truth if self.truth else 1.0

    @property
    def precision(self) -> float:
        return self.matched / self.detected if self.detected else 1.0

    @property
    def gap(self) -> int:
        return self.detected - self.truth


def e2_deliveries(deliveries: list[Delivery], balls: list[Ball]) -> E2:
    """Match deliveries to Cricsheet balls by innings + overs, then by order."""
    matched = 0
    for innings in (1, 2):
        truth = sorted(
            (b for b in balls if b.innings == innings), key=lambda b: b.legal_balls_after
        )
        used = [False] * len(truth)
        ours = sorted((d for d in deliveries if d.innings == innings), key=lambda d: d.start_s)
        unreadable = []
        for d in ours:
            key = _legal(d.over_ball)
            if key is None:
                unreadable.append(d)
                continue
            cands = [i for i, b in enumerate(truth) if not used[i] and b.legal_balls_after == key]
            if cands:
                legal_first = sorted(cands, key=lambda i: not truth[i].legal)
                used[legal_first[0]] = True
                matched += 1
            else:
                unreadable.append(d)
        free = used.count(False)
        matched += min(len(unreadable), free)  # by order: each leftover takes a free ball
    return E2(detected=len(deliveries), truth=len(balls), matched=matched)


@dataclass
class E3:
    total: int = 0
    contained: int = 0
    offsets: list[float] = field(default_factory=list)  # clip start - annotated start (s)
    missing: list[str] = field(default_factory=list)

    @property
    def contained_ratio(self) -> float:
        return self.contained / self.total if self.total else 1.0

    @property
    def median_offset(self) -> float | None:
        return round(statistics.median(self.offsets), 3) if self.offsets else None

    @property
    def p90_offset(self) -> float | None:
        if not self.offsets:
            return None
        ordered = sorted(self.offsets)
        return round(ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))], 3)


def _find_event(a: Annotation, events: list[Event]) -> Event | None:
    exact = [
        e
        for e in events
        if e.type == a.type and e.innings == a.innings and e.over_ball == a.over_ball
    ]
    if exact:
        return exact[0]
    near = [
        e for e in events if e.type == a.type and abs(e.moment_s - a.t_moment_s) <= MATCH_WINDOW_S
    ]
    return min(near, key=lambda e: abs(e.moment_s - a.t_moment_s)) if near else None


def e3_clips(
    annotations: list[Annotation],
    events: list[Event],
    post_moment_s: float = POST_MOMENT_S,
    start_tolerance_s: float = START_TOLERANCE_S,
) -> E3:
    """Share of annotated boundaries/wickets whose clip contains the whole moment."""
    result = E3()
    for a in annotations:
        if a.type not in ("four", "six", "wicket"):
            continue
        result.total += 1
        e = _find_event(a, events)
        if e is None:
            result.missing.append(f"{a.innings}:{a.over_ball} {a.type}")
            continue
        offset = e.clip.start_s - a.t_start_s
        result.offsets.append(round(offset, 3))
        if offset <= start_tolerance_s and e.clip.end_s >= a.t_moment_s + post_moment_s:
            result.contained += 1
    return result


def runtime(summary: Summary) -> dict:
    return {"processing_s": summary.processing_s, "stages": dict(summary.stage_timings)}
