"""Goal state machine and halves (second half of stage 4, ``read_score``).

Turns per-crop readings into ``score_timeline.json`` and ``score_events.json``, following
"Goal state machine (stage 4)" in ARCHITECTURE.md.

**Confirming a score.** A reading is copied to every crop until the crop changes, so many
readings can come from one OCR call: on the dev matches, every misread that looked like a goal
was a single OCR result copied to 4-9 crops. A new score is therefore accepted only once at
least ``CONFIRM_TEXTS`` different OCR results agree (different raw text: the clock in it has
moved on), or once it has held for ``CONFIRM_HOLD_READS`` clock reads, for broadcasts whose
clock is frozen. It also needs ``score_confirm`` readings. The goal is dated to the score's
first reading.

**Changes.** Exactly one side +1 is a goal. One side -1 within ``goal_overturn_window_s`` of
that side's last goal overturns it. Anything else is rejected, except that a score which rose
by more than one goal and holds for ``RESYNC_S`` is adopted without events, so that a missed
goal can't stop every later goal being found.

**Halves.** A new half starts where the clock is discontinuous and stays that way: it jumps
back, or after the graphic was hidden for ``BREAK_MIN_S`` it no longer matches the time that
passed. A clock that stops for ``half_gap_s`` while visible is also a break. ``in_play`` is
true from a half's first clock reading to its last.
"""

from __future__ import annotations

import bisect
import statistics
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, field

from reel.common.config import ScoreboardConfig
from reel.common.logging import get_logger
from reel.common.models import ScoreEvent, ScoreReading, ScoreTimelineEntry

log = get_logger("scoreboard.state")

CONFIRM_TEXTS = 2  # separate OCR results that must agree on a new score
CONFIRM_HOLD_READS = 1.5  # ... or it must hold this many clock-read intervals
RESYNC_S = 300.0  # a score that rose by several goals is adopted, silently, after this long
JUMP_TOL_S = 60.0  # a clock this far off the time that passed is discontinuous
BREAK_MIN_S = 10.0  # a gap in the clock this long can hide a half-time break
PERSIST_S = 60.0  # a new clock must hold for this long (a misread clock doesn't)
PERSIST_SHARE = 0.8  # ... in this share of readings
HALF_CLOCK_S = 45 * 60  # the second half's clock starts here
SPLIT_MIN_S = 600.0  # a clock running this long past 45:00 is the second half

Score = tuple[int, int]


@dataclass
class _Half:
    number: int
    start_s: float
    end_s: float
    offsets: list[tuple[float, float]] = field(default_factory=list)  # (time, clock - time)


def _clock_points(readings: Sequence[ScoreReading]) -> list[tuple[float, int]]:
    return [(r.time_s, r.clock_s) for r in readings if r.visible and r.clock_s is not None]


def _persists(points: Sequence[tuple[float, int]], i: int, offset: float) -> bool:
    ahead = [(t, c) for t, c in points[i:] if t - points[i][0] <= PERSIST_S]
    agree = sum(abs((c - t) - offset) <= JUMP_TOL_S for t, c in ahead)
    return agree >= PERSIST_SHARE * len(ahead)


def find_halves(readings: Sequence[ScoreReading], cfg: ScoreboardConfig) -> list[_Half]:
    """Halves from the clock readings, in time order.

    Each reading is compared with the current half's clock line (the median clock offset over
    the last ``PERSIST_S``), not with the reading before it: a misread clock just before the
    graphic hid otherwise made the next, correct reading look like a jump.
    """
    points = _clock_points(readings)
    if not points:
        return []
    t0, c0 = points[0]
    halves = [_Half(1, t0, t0, [(t0, c0 - t0)])]
    line: deque[tuple[float, float]] = deque([(t0, c0 - t0)])  # (time, offset) on the line
    last_t, last_clock = t0, c0
    frozen_since: float | None = None
    for i in range(1, len(points)):
        t, clock = points[i]
        offset = clock - t
        while len(line) > 1 and t - line[0][0] > PERSIST_S:
            line.popleft()
        off = offset - statistics.median(o for _, o in line)
        gap = t - last_t
        jumped = off < -JUMP_TOL_S or (gap >= BREAK_MIN_S and abs(off) > JUMP_TOL_S)
        restarted = (
            frozen_since is not None and clock > last_clock and t - frozen_since >= cfg.half_gap_s
        )
        if (jumped and _persists(points, i, offset)) or restarted:
            halves.append(_Half(len(halves) + 1, t, t))
            line, frozen_since = deque(), None
        elif abs(off) > JUMP_TOL_S:
            if not _persists(points, i, offset):
                halves[-1].end_s = t
                continue  # a misread clock: keep it off the line
            line = deque()  # the clock moved on for good within the half
        else:
            if clock > last_clock:
                frozen_since = None
            elif frozen_since is None:
                frozen_since = last_t
            if frozen_since is None or t - frozen_since < cfg.half_gap_s:
                halves[-1].end_s = t
        line.append((t, offset))
        halves[-1].offsets.append((t, offset))
        last_t, last_clock = t, clock
    return _split_continuous(halves) if len(halves) == 1 else halves


def _split_continuous(halves: list[_Half]) -> list[_Half]:
    """Split one long half where its clock passes 45:00 and runs on for ``SPLIT_MIN_S``.

    SoccerNet cuts each half's file at 45:00, so a joined match has no break and its clock runs
    straight from the first half's 45:00 into the second half's. Real broadcasts have a break,
    so they already have two halves by now.
    """
    (half,) = halves
    clocks = [(t, round(t + o)) for t, o in half.offsets]
    i = next((k for k, (_, c) in enumerate(clocks) if c >= HALF_CLOCK_S), None)
    if i is None or i == 0 or clocks[-1][0] - clocks[i][0] < SPLIT_MIN_S:
        return halves
    first = _Half(1, half.start_s, clocks[i - 1][0], half.offsets[:i])
    second = _Half(2, clocks[i][0], half.end_s, half.offsets[i:])
    return [first, second]


def _half_at(halves: Sequence[_Half], t: float) -> _Half | None:
    starts = [h.start_s for h in halves]
    i = bisect.bisect_right(starts, t) - 1
    return halves[i] if i >= 0 else None


def _clock_at(half: _Half | None, t: float) -> int | None:
    """Clock at ``t``, counted on from the half's nearest clock reading."""
    if half is None or not half.offsets or t < half.start_s:
        return None
    times = [o[0] for o in half.offsets]
    i = min(max(bisect.bisect_left(times, t), 0), len(times) - 1)
    near = min((half.offsets[j] for j in (i - 1, i) if 0 <= j < len(times)),
               key=lambda o: abs(o[0] - t))
    return max(0, round(t + near[1]))


@dataclass
class _Candidate:
    first_s: float
    readings: int = 0
    texts: set[str] = field(default_factory=set)


@dataclass
class _Goal:
    time_s: float
    event: ScoreEvent


def _transition(old: Score, new: Score) -> str:
    dh, da = new[0] - old[0], new[1] - old[1]
    if (dh, da) in ((1, 0), (0, 1)):
        return "goal"
    if (dh, da) in ((-1, 0), (0, -1)):
        return "drop"
    if dh >= 0 and da >= 0:
        return "jump"
    return "invalid"


def build_timeline(
    readings: Sequence[ScoreReading], cfg: ScoreboardConfig
) -> tuple[list[ScoreTimelineEntry], list[ScoreEvent]]:
    """Validated score timeline and events from per-crop readings."""
    readings = sorted(readings, key=lambda r: r.time_s)
    halves = find_halves(readings, cfg)
    hold_s = CONFIRM_HOLD_READS * cfg.clock_read_s

    changes: list[tuple[float, Score]] = []  # (time the graphic first showed it, score)
    events: list[ScoreEvent] = []
    goals: dict[str, _Goal] = {}  # each side's last goal that still stands
    score: Score | None = None
    candidates: dict[Score, _Candidate] = {}

    def event(kind: str, t: float, side: str | None, after: Score) -> ScoreEvent:
        half = _half_at(halves, t)
        return ScoreEvent(
            type=kind, time_s=t, side=side, home=after[0], away=after[1],
            half=half.number if half else 1, clock_s=_clock_at(half, t),
        )

    for r in readings:
        if not r.visible or r.home is None or r.away is None:
            continue
        value = (r.home, r.away)
        if score is None and value == (0, 0):
            score = value  # kick-off: nothing to confirm, and the first goal must not be lost
            continue
        if value == score:
            candidates.clear()  # anything else seen since was a misread
            continue
        cand = candidates.setdefault(value, _Candidate(r.time_s))
        cand.readings += 1
        cand.texts.add(r.raw_text)
        held = r.time_s - cand.first_s
        agreed = len(cand.texts) >= CONFIRM_TEXTS or held >= hold_s
        if cand.readings < cfg.score_confirm or not agreed:
            continue

        if score is None:  # the first score shown, whatever it is
            score = value
            changes.append((cand.first_s, value))
            candidates.clear()
            continue
        kind = _transition(score, value)
        if kind == "goal":
            side = "home" if value[0] > score[0] else "away"
            ev = event("goal", cand.first_s, side, value)
            events.append(ev)
            goals[side] = _Goal(cand.first_s, ev)
        elif kind == "drop":
            side = "home" if value[0] < score[0] else "away"
            goal = goals.get(side)
            if goal is None or cand.first_s - goal.time_s > cfg.goal_overturn_window_s:
                continue  # rejected: the score stands
            goal.event.overturned = True
            events.append(event("goal_overturned", cand.first_s, side, value))
            del goals[side]
        elif kind == "jump" and held >= RESYNC_S:
            log.warning("Score jumped from %s to %s and held; adopting it without events",
                        score, value)
            goals.clear()
        else:
            continue  # rejected, for now at least
        score = value
        changes.append((cand.first_s, value))
        candidates.clear()

    for half in halves:
        at_start = _score_at(changes, half.start_s)
        events.append(event("half_start", half.start_s, None, at_start))
    events.sort(key=lambda e: (e.time_s, e.type != "half_start"))

    timeline = []
    for r in readings:
        half = _half_at(halves, r.time_s)
        home, away = _score_at(changes, r.time_s)
        in_play = half is not None and half.start_s <= r.time_s <= half.end_s
        timeline.append(
            ScoreTimelineEntry(
                time_s=r.time_s, home=home, away=away, visible=r.visible,
                half=half.number if half else 1,
                clock_s=r.clock_s if r.clock_s is not None else (
                    _clock_at(half, r.time_s) if in_play else None
                ),
                in_play=in_play,
            )
        )
    log.info(
        "Score timeline: %d halves, %d goals (%d overturned)",
        len(halves),
        sum(e.type == "goal" for e in events),
        sum(e.type == "goal_overturned" for e in events),
    )
    return timeline, events


def _score_at(changes: Sequence[tuple[float, Score]], t: float) -> Score:
    current: Score = (0, 0)
    for when, value in changes:
        if when > t:
            break
        current = value
    return current
