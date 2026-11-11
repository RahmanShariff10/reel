"""Tests for slice-41-goal-state.

Acceptance criteria:
- Synthetic readings: every scheduled goal is emitted on the right side at the update time
  (+-1 s).
- A one-off misread 7-0 between 1-0 readings emits no event.
- A jump from 1-0 to 3-0 is rejected.
- 1-0 back to 0-0 within 300 s: the goal is overturned and goal_overturned is emitted.
- The same drop after 300 s is rejected and the score stands.
- The half-time break emits half_start; in_play is false during it and before kick-off.
- A clock that restarts at 45:00 or at 00:00 is handled as a new half.
- Extra time with the clock running past 90:00 continues without a false half.

Also from the build order (fix H): a misread copied from one OCR call to many readings, as
seen on the dev matches, emits no event.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from reel.common.config import ScoreboardConfig, load_config
from reel.common.models import (
    Scorebox,
    ScoreEvent,
    ScoreReading,
    ScoreTimelineEntry,
    read_model,
    write_model,
)
from reel.common.paths import JobPaths
from reel.jobs.pipeline import PipelineContext
from reel.scoreboard.parse import find_goals
from reel.scoreboard.score_stage import is_valid_read_score, run_read_score
from reel.scoreboard.state import build_timeline
from tests.fixtures.make_football import (
    build_schedule,
    clock_seconds_at,
    clock_text_at,
    score_text_at,
)

CFG = ScoreboardConfig()
STEP = 0.5  # crops per second, as scan writes them


def clock_text(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def reading(t: float, score: tuple[int, int] | None, clock: int | None,
            text: str | None = None) -> ScoreReading:
    if score is None and clock is None:
        return ScoreReading(time_s=t, visible=False)
    shown = f"ARS {score[0]}-{score[1]} CHE" if score else "ARS CHE"
    return ScoreReading(
        time_s=t,
        raw_text=text if text is not None else f"{shown} {clock_text(clock or 0)}",
        home=score[0] if score else None,
        away=score[1] if score else None,
        clock_s=clock,
        visible=True,
    )


def run(segments) -> list[ScoreReading]:
    """Readings at 2 per second from ``(start, end, score, clock_at_start)`` segments.

    ``score`` None hides the graphic. Each reading has its own raw text, as if OCR'd.
    """
    out = []
    for start, end, score, clock0 in segments:
        t = start
        while t < end - 1e-9:
            clock = None if score is None else int(clock0 + (t - start))
            out.append(reading(t, score, clock))
            t = round(t + STEP, 3)
    return out


def goals(events: list[ScoreEvent]) -> list[ScoreEvent]:
    return [e for e in events if e.type == "goal"]


def score_at(timeline: list[ScoreTimelineEntry], t: float) -> tuple[int, int]:
    entry = max((e for e in timeline if e.time_s <= t), key=lambda e: e.time_s)
    return entry.home, entry.away


# ---------------------------------------------------------------------------
# Readings from the synthetic football schedule
# ---------------------------------------------------------------------------


def schedule_readings(schedule: dict) -> list[ScoreReading]:
    out, t = [], 0.0
    while t < schedule["duration_s"]:
        text = score_text_at(schedule, t)
        if text is None:
            out.append(ScoreReading(time_s=t, visible=False))
        else:
            home, away = find_goals(text)
            out.append(ScoreReading(
                time_s=t, raw_text=f"{text} {clock_text_at(schedule, t)}", home=home, away=away,
                clock_s=clock_seconds_at(schedule, t), visible=True,
            ))
        t = round(t + STEP, 3)
    return out


@pytest.fixture(scope="module", params=[2700, 0], ids=["restart-45:00", "restart-00:00"])
def synthetic(request):
    schedule = build_schedule(duration_s=600.0, second_half_clock_s=request.param)
    timeline, events = build_timeline(schedule_readings(schedule), CFG)
    return schedule, timeline, events


class TestSyntheticSchedule:
    def test_every_goal_on_the_right_side_at_the_update_time(self, synthetic) -> None:
        schedule, _, events = synthetic
        found = goals(events)
        assert len(found) == len(schedule["goals"])
        for truth, ev in zip(schedule["goals"], found):
            assert ev.side == truth["side"]
            assert abs(ev.time_s - truth["t_update_s"]) <= 1.0
            assert ev.half == truth["half"]
            assert ev.overturned == truth["overturned"]

    def test_overturned_goal(self, synthetic) -> None:
        schedule, _, events = synthetic
        truth = next(g for g in schedule["goals"] if g["overturned"])
        undone = [e for e in events if e.type == "goal_overturned"]
        assert len(undone) == 1 and undone[0].side == truth["side"]
        assert abs(undone[0].time_s - truth["t_overturn_s"]) <= 1.0

    def test_halves_and_in_play(self, synthetic) -> None:
        schedule, timeline, events = synthetic
        starts = [e for e in events if e.type == "half_start"]
        assert [e.half for e in starts] == [1, 2]
        for ev, half in zip(starts, schedule["halves"]):
            assert abs(ev.time_s - half["start_s"]) <= 1.0
        h1, h2 = schedule["halves"]
        for entry in timeline:
            t = entry.time_s
            if t < h1["start_s"] or h1["end_s"] + 1 < t < h2["start_s"]:
                assert not entry.in_play, entry  # before kick-off and at half-time
            elif h1["start_s"] + 1 < t < h1["end_s"] - 1 or h2["start_s"] + 1 < t < h2["end_s"] - 1:
                assert entry.in_play, entry
                assert entry.half == (1 if t < h1["end_s"] else 2)

    def test_final_score(self, synthetic) -> None:
        schedule, timeline, _ = synthetic
        home, away = find_goals(schedule["final_score"])
        assert (timeline[-1].home, timeline[-1].away) == (home, away)

    def test_hidden_in_play_readings_get_the_clock(self, synthetic) -> None:
        schedule, timeline, _ = synthetic
        r0, r1 = schedule["replays"][0]
        inside = [e for e in timeline if r0 + 0.5 < e.time_s < r1 - 0.5]
        assert inside and all(not e.visible and e.in_play for e in inside)
        assert all(abs(e.clock_s - clock_seconds_at(schedule, e.time_s)) <= 1 for e in inside)


# ---------------------------------------------------------------------------
# Misreads, jumps and overturns
# ---------------------------------------------------------------------------


class TestMisreads:
    def test_one_off_misread_emits_nothing(self) -> None:
        readings = run([(0, 60, (1, 0), 600)])
        readings[60] = reading(30.0, (7, 0), 630)
        _, events = build_timeline(readings, CFG)
        assert goals(events) == []

    def test_misread_copied_from_one_ocr_call_emits_nothing(self) -> None:
        # On the dev matches, every misread that looked like a goal was one OCR result copied
        # to 4-9 readings, e.g. 0-0 read as 0-1 for 4 s.
        readings = run([(0, 120, (0, 0), 600)])
        for i in range(100, 109):
            readings[i] = reading(readings[i].time_s, (0, 1), 650, text="OM 0 1 PARIS SG 10:50")
        timeline, events = build_timeline(readings, CFG)
        assert goals(events) == []
        assert score_at(timeline, 119.5) == (0, 0)

    def test_real_change_confirmed_by_a_second_ocr_result(self) -> None:
        # The reader OCRs a changed crop once, then copies it until the next clock read.
        readings = run([(0, 60, (1, 0), 600), (60, 120, (2, 0), 660)])
        for i in range(120, 160):
            readings[i] = reading(readings[i].time_s, (2, 0), 660, text="ARS 2-0 CHE 11:00")
        _, events = build_timeline(readings, CFG)
        assert [(e.side, e.time_s, e.home, e.away) for e in goals(events)] == [
            ("home", 60.0, 2, 0)
        ]

    def test_first_goal_soon_after_kick_off(self) -> None:
        # 0-0 read once at kick-off, then a goal before any second OCR result of 0-0.
        readings = [reading(i * STEP, (0, 0), 0, text="ARS 0-0 CHE 00:00") for i in range(40)]
        readings += run([(20, 80, (1, 0), 20)])
        _, events = build_timeline(readings, CFG)
        assert [(e.side, e.time_s) for e in goals(events)] == [("home", 20.0)]

    def test_video_starting_mid_match_emits_no_goal_for_the_opening_score(self) -> None:
        readings = run([(0, 120, (2, 1), 3000)])
        timeline, events = build_timeline(readings, CFG)
        assert goals(events) == [] and score_at(timeline, 119.5) == (2, 1)

    def test_frozen_clock_confirmed_by_holding(self) -> None:
        readings = run([(0, 60, (1, 0), 2700)])
        readings += [reading(60 + i * STEP, (1, 1), 2700, text="ARS 1-1 CHE 45:00")
                     for i in range(120)]  # 60 s, every OCR result identical
        _, events = build_timeline(readings, CFG)
        assert [(e.side, e.time_s) for e in goals(events)] == [("away", 60.0)]


class TestJumps:
    def test_jump_by_two_goals_rejected(self) -> None:
        readings = run([(0, 60, (1, 0), 600), (60, 180, (3, 0), 660)])
        timeline, events = build_timeline(readings, CFG)
        assert goals(events) == []
        assert score_at(timeline, 179.5) == (1, 0)

    def test_long_held_jump_adopted_without_events(self) -> None:
        # A goal was missed: don't let it stop every later goal being found.
        readings = run([(0, 60, (1, 0), 600), (60, 420, (3, 0), 660), (420, 480, (3, 1), 1020)])
        timeline, events = build_timeline(readings, CFG)
        assert [(e.side, e.home, e.away) for e in goals(events)] == [("away", 3, 1)]
        assert score_at(timeline, 400.0) == (3, 0)


class TestOverturn:
    def test_drop_within_300s_overturns_the_goal(self) -> None:
        readings = run([(0, 60, (0, 0), 600), (60, 150, (1, 0), 660), (150, 240, (0, 0), 750)])
        timeline, events = build_timeline(readings, CFG)
        goal = goals(events)
        assert len(goal) == 1 and goal[0].overturned
        undone = [e for e in events if e.type == "goal_overturned"]
        assert [(e.side, e.time_s, e.home, e.away) for e in undone] == [("home", 150.0, 0, 0)]
        assert score_at(timeline, 100.0) == (1, 0) and score_at(timeline, 239.5) == (0, 0)

    def test_drop_after_300s_rejected_and_the_score_stands(self) -> None:
        readings = run([(0, 60, (0, 0), 600), (60, 400, (1, 0), 660), (400, 700, (0, 0), 1000)])
        timeline, events = build_timeline(readings, CFG)
        assert not goals(events)[0].overturned
        assert not [e for e in events if e.type == "goal_overturned"]
        assert score_at(timeline, 699.5) == (1, 0)

    def test_overturn_after_the_other_side_scored(self) -> None:
        readings = run([
            (0, 60, (0, 0), 600), (60, 120, (1, 0), 660),
            (120, 180, (1, 1), 720), (180, 240, (0, 1), 780),
        ])
        _, events = build_timeline(readings, CFG)
        assert [(e.side, e.overturned) for e in goals(events)] == [("home", True), ("away", False)]


# ---------------------------------------------------------------------------
# Halves
# ---------------------------------------------------------------------------


def halves(events: list[ScoreEvent]) -> list[tuple[int, float]]:
    return [(e.half, e.time_s) for e in events if e.type == "half_start"]


class TestHalves:
    @pytest.mark.parametrize("restart", [2700, 0], ids=["45:00", "00:00"])
    def test_break_then_restart(self, restart: int) -> None:
        readings = run([
            (0, 10, None, 0), (10, 300, (0, 0), 2400),  # pre-match, then 40:00-44:50
            (300, 1200, None, 0),  # 15 minutes of half-time, graphic hidden
            (1200, 1500, (0, 0), restart),
        ])
        timeline, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 10.0), (2, 1200.0)]
        assert not any(e.in_play for e in timeline if e.time_s < 10 or 300 < e.time_s < 1200)
        assert all(e.half == 2 for e in timeline if e.time_s >= 1200)

    def test_joined_halves_without_a_break(self) -> None:
        # SoccerNet's two half files joined: 47:30 straight into 45:00.
        readings = run([(0, 150, (0, 0), 2700), (150, 300, (0, 0), 2700)])
        _, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 0.0), (2, 150.0)]

    def test_soccernet_halves_joined_at_45_00(self) -> None:
        # SoccerNet cuts each half at 45:00: joined, the clock runs on without a break.
        readings = run([(0, 2700, (0, 0), 0), (2700, 5400, (0, 0), 2700)])
        timeline, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 0.0), (2, 2700.0)]
        assert all(e.in_play for e in timeline)

    def test_one_half_alone_is_not_split(self) -> None:
        readings = run([(0, 2760, (0, 0), 0)])  # a first half running a minute past 45:00
        _, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 0.0)]

    def test_extra_time_past_90_00_is_one_half(self) -> None:
        readings = run([
            (0, 300, (1, 1), 85 * 60), (300, 308, None, 0),  # a replay hides the graphic
            (308, 600, (1, 1), 85 * 60 + 308),  # on past 90:00 to 95:00
        ])
        timeline, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 0.0)]
        assert all(e.in_play for e in timeline)

    def test_misread_clock_is_not_a_half(self) -> None:
        readings = run([(0, 300, (0, 0), 1200)])
        for i in range(200, 210):  # five seconds of a clock read 5 minutes slow
            r = readings[i]
            readings[i] = reading(r.time_s, (0, 0), r.clock_s - 300)
        _, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 0.0)]

    def test_misread_clock_before_a_hidden_gap_is_not_a_half(self) -> None:
        # Seen on the dev matches: a misread clock read, then the graphic hid for a replay.
        readings = run([(0, 200, (0, 0), 1200), (200, 215, None, 0), (215, 400, (0, 0), 1415)])
        for i in range(390, 400):  # the last 5 s before the gap read 2 minutes fast
            r = readings[i]
            readings[i] = reading(r.time_s, (0, 0), r.clock_s + 120)
        _, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 0.0)]

    def test_frozen_stoppage_clock_is_not_a_half(self) -> None:
        readings = run([(0, 120, (0, 0), 2580)])  # 43:00-45:00
        readings += [reading(120 + i * STEP, (0, 0), 2700) for i in range(360)]  # frozen 3 min
        _, events = build_timeline(readings, CFG)
        assert halves(events) == [(1, 0.0)]


# ---------------------------------------------------------------------------
# The stage
# ---------------------------------------------------------------------------


class TestStage:
    def test_synthetic_broadcast(self, scanned_match: PipelineContext, synthetic_match) -> None:
        run_read_score(scanned_match)
        assert is_valid_read_score(scanned_match)
        events = read_model(scanned_match.paths.score_events_json, list[ScoreEvent])
        first = synthetic_match.schedule["goals"][0]
        assert goals(events), events
        assert goals(events)[0].side == first["side"]
        assert abs(goals(events)[0].time_s - first["t_update_s"]) <= 1.0
        assert [e.half for e in events if e.type == "half_start"] == [1, 2]
        timeline = read_model(scanned_match.paths.score_timeline_json, list[ScoreTimelineEntry])
        readings = read_model(scanned_match.paths.score_readings_json, list[ScoreReading])
        assert len(timeline) == len(readings)

    def test_no_score_graphic(self, tmp_path: Path) -> None:
        paths = JobPaths("job", data_dir=tmp_path)
        paths.ensure_job_dir()
        write_model(paths.scorebox_json, Scorebox(found=False))
        ctx = PipelineContext(job_id="job", db_path=tmp_path / "db", paths=paths,
                              config=load_config())
        run_read_score(ctx)
        assert is_valid_read_score(ctx)
        assert read_model(paths.score_events_json, list[ScoreEvent]) == []
        assert read_model(paths.score_timeline_json, list[ScoreTimelineEntry]) == []
