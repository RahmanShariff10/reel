"""Evaluation metrics against SoccerNet labels (definitions in ARCHITECTURE.md).

E0 score graphic found, E1 goals, E2 key actions, E3 goal clips, E5 reel quality and
runtime. E4 (ablation) is in slice 26.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from reel.common.models import Event, ReelPlan, ScoreTimelineEntry

from eval.soccernet import KEY_ACTIONS, Label, to_match_time

GOAL_WINDOW_S = 30.0
KEY_ACTION_WINDOW_S = 15.0
CLIP_MARGIN_S = 3.0
RANDOM_DRAWS = 20
RANDOM_SEED = 42
ALL_MODE_TYPES = {"goal", "penalty", "red_card", "chance"}

Interval = tuple[float, float]


def goal_times(labels: Sequence[Label], first_half_s: float) -> list[float]:
    """Times of ``Goal`` labels in the joined match file, in order."""
    return sorted(to_match_time(lab, first_half_s) for lab in labels if lab.label == "Goal")


def key_action_times(labels: Sequence[Label], first_half_s: float) -> list[float]:
    """Times of key-action labels in the joined match file, in order."""
    return sorted(to_match_time(lab, first_half_s) for lab in labels if lab.label in KEY_ACTIONS)


@dataclass
class Detection:
    """Counts for matching detected events to labels."""

    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None


def _real_goals(events: Sequence[Event]) -> list[Event]:
    return [e for e in events if e.type == "goal" and not e.overturned]


def e1_goals(
    events: Sequence[Event], goals: Sequence[float], window_s: float = GOAL_WINDOW_S
) -> Detection:
    """Match each detected goal to the nearest unused goal label within the window."""
    used = [False] * len(goals)
    result = Detection()
    for event in sorted(_real_goals(events), key=lambda e: e.moment_s):
        best, best_dist = None, None
        for i, t in enumerate(goals):
            dist = abs(event.moment_s - t)
            if not used[i] and dist <= window_s and (best_dist is None or dist < best_dist):
                best, best_dist = i, dist
        if best is None:
            result.fp += 1
        else:
            used[best] = True
            result.tp += 1
    result.fn = used.count(False)
    return result


@dataclass
class Coverage:
    """How many labelled things were covered."""

    found: int = 0
    total: int = 0

    @property
    def ratio(self) -> float | None:
        return self.found / self.total if self.total else None


def all_mode_events(events: Sequence[Event], scorebox_found: bool = True) -> list[Event]:
    """Events eligible for the ``all`` reel, following the selection rule."""
    types = ALL_MODE_TYPES if scorebox_found else ALL_MODE_TYPES | {"moment"}
    return [e for e in events if e.type in types and not e.overturned]


def e2_key_actions(
    events: Sequence[Event],
    actions: Sequence[float],
    scorebox_found: bool = True,
    window_s: float = KEY_ACTION_WINDOW_S,
) -> Coverage:
    """Share of key actions with an ``all``-mode event within the window."""
    eligible = [e.moment_s for e in all_mode_events(events, scorebox_found)]
    found = sum(any(abs(m - t) <= window_s for m in eligible) for t in actions)
    return Coverage(found=found, total=len(actions))


def e3_goal_clips(
    events: Sequence[Event], goals: Sequence[float], margin_s: float = CLIP_MARGIN_S
) -> Coverage:
    """Share of goal labels with a goal clip covering label - margin to label + margin."""
    clips = [e.clip for e in _real_goals(events)]

    def covered(t: float) -> bool:
        return any(c.start_s <= t - margin_s and c.end_s >= t + margin_s for c in clips)

    return Coverage(found=sum(covered(t) for t in goals), total=len(goals))


def in_play_intervals(
    timeline: Sequence[ScoreTimelineEntry], duration_s: float
) -> list[Interval]:
    """Continuous in-play stretches; the whole video when the timeline has none."""
    intervals: list[Interval] = []
    start: float | None = None
    last = 0.0
    for entry in sorted(timeline, key=lambda e: e.time_s):
        if entry.in_play and start is None:
            start = entry.time_s
        elif not entry.in_play and start is not None:
            intervals.append((start, entry.time_s))
            start = None
        last = entry.time_s
    if start is not None:
        intervals.append((start, last))
    return intervals or [(0.0, duration_s)]


def _contains_action(start: float, end: float, actions: Sequence[float]) -> bool:
    return any(start <= t <= end for t in actions)


def _random_share(
    lengths: Sequence[float],
    actions: Sequence[float],
    intervals: Sequence[Interval],
    rng: random.Random,
) -> float:
    hits = 0
    for length in lengths:
        room = [(a, b - length) for a, b in intervals if b - length > a]
        if not room:
            continue
        a, latest = rng.choices(room, weights=[b - a for a, b in room])[0]
        start = rng.uniform(a, latest)
        hits += _contains_action(start, start + length, actions)
    return hits / len(lengths)


@dataclass
class ReelQuality:
    clips: int = 0
    with_action: int = 0
    random_share: float | None = None

    @property
    def share(self) -> float | None:
        return self.with_action / self.clips if self.clips else None


def e5_reel_quality(
    plan: ReelPlan,
    actions: Sequence[float],
    intervals: Sequence[Interval],
    seed: int = RANDOM_SEED,
    draws: int = RANDOM_DRAWS,
) -> ReelQuality:
    """Share of reel clips containing a key action, against random clips of the same lengths."""
    if not plan.clips:
        return ReelQuality()
    lengths = [c.end_s - c.start_s for c in plan.clips]
    rng = random.Random(seed)
    baseline = sum(_random_share(lengths, actions, intervals, rng) for _ in range(draws)) / draws
    return ReelQuality(
        clips=len(plan.clips),
        with_action=sum(_contains_action(c.start_s, c.end_s, actions) for c in plan.clips),
        random_share=baseline,
    )
