"""Tests for slice-12-match-state.

Acceptance criteria:
- Synthetic video: every scheduled score change produces exactly one event of the right
  type and delta, within 1 s of the scheduled time.
- A single misread crop injected into readings produces no event.
- A run jump of 20 in one change is rejected.
- The scheduled innings reset emits innings_start and later events have innings 2.
- The scheduled DRS reversal marks the wicket overturned and emits wicket_overturned.
- A hidden-box period followed by a changed score emits exactly the correct event after
  the box reappears.
- scorebox.json with found: false → empty outputs and the stage succeeds.
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
from reel.scoreboard.score_stage import is_valid_read_score, run_read_score
from reel.scoreboard.state import build_timeline

CFG = ScoreboardConfig()
EXPECTED_TYPE = {
    "runs": "runs",
    "four": "runs",
    "six": "runs",
    "wicket": "wicket",
    "wicket_overturned": "wicket_overturned",
    "innings_start": "innings_start",
}


def readings(spec: list[tuple[float, int | None, int | None, float | None]]) -> list[ScoreReading]:
    """Build readings from (time, runs, wickets, overs); runs=None means box hidden."""
    return [
        ScoreReading(time_s=t, runs=r, wickets=w, overs=o, visible=r is not None)
        for t, r, w, o in spec
    ]


def steady(t0: float, n: int, runs: int, wkts: int, overs: float) -> list[tuple]:
    return [(t0 + 0.5 * i, runs, wkts, overs) for i in range(n)]


@pytest.fixture(scope="module")
def synthetic_events(scanned_match: PipelineContext) -> list[ScoreEvent]:
    run_read_score(scanned_match)
    return read_model(scanned_match.paths.score_events_json, list[ScoreEvent])


class TestSynthetic:
    def test_every_change_one_event_within_1s(self, synthetic_events, synthetic_match):
        expected = [
            c for c in synthetic_match.schedule["score_changes"] if c["event"] in EXPECTED_TYPE
        ]
        assert len(synthetic_events) == len(expected)
        for change in expected:
            matches = [
                e
                for e in synthetic_events
                if e.type == EXPECTED_TYPE[change["event"]]
                and e.runs_delta == change["runs_delta"]
                and e.wicket_delta == change["wicket_delta"]
                and abs(e.time_s - change["time_s"]) <= 1.0
            ]
            assert len(matches) == 1, change

    def test_innings_two_after_reset(self, synthetic_events) -> None:
        start = next(e for e in synthetic_events if e.type == "innings_start")
        assert start.innings == 2
        assert all(e.innings == 2 for e in synthetic_events if e.time_s > start.time_s)
        assert all(e.innings == 1 for e in synthetic_events if e.time_s < start.time_s)

    def test_drs_reversal(self, synthetic_events) -> None:
        wickets = [e for e in synthetic_events if e.type == "wicket"]
        assert sum(w.overturned for w in wickets) == 1
        assert any(e.type == "wicket_overturned" for e in synthetic_events)

    def test_timeline_written(self, scanned_match: PipelineContext, synthetic_events) -> None:
        timeline = read_model(scanned_match.paths.score_timeline_json, list[ScoreTimelineEntry])
        assert len(timeline) > 200 and any(not e.visible for e in timeline)
        assert is_valid_read_score(scanned_match)


class TestRules:
    def test_single_misread_ignored(self) -> None:
        spec = steady(0, 6, 140, 2, 15.0) + [(3.0, 148, 2, 15.0)] + steady(3.5, 6, 140, 2, 15.0)
        _, events = build_timeline(readings(spec), CFG)
        assert events == []

    def test_run_jump_of_20_rejected(self) -> None:
        spec = steady(0, 4, 140, 2, 15.0) + steady(2, 4, 160, 2, 15.1)
        _, events = build_timeline(readings(spec), CFG)
        assert events == []

    def test_overs_going_backwards_ignored(self) -> None:
        spec = steady(0, 4, 140, 2, 15.3) + steady(2, 4, 140, 2, 15.1)
        _, events = build_timeline(readings(spec), CFG)
        assert events == []

    def test_change_after_hidden_period(self) -> None:
        spec = (
            steady(0, 4, 140, 2, 15.0)
            + [(2.0 + 0.5 * i, None, None, None) for i in range(6)]
            + steady(5.0, 4, 144, 2, 15.1)
        )
        _, events = build_timeline(readings(spec), CFG)
        assert len(events) == 1
        e = events[0]
        assert (e.type, e.runs_delta, e.time_s) == ("runs", 4, 5.0)

    def test_drs_window_from_config(self) -> None:
        spec = (
            steady(0, 4, 140, 2, 15.0) + steady(2, 4, 140, 3, 15.1) + steady(200, 4, 140, 2, 15.1)
        )
        _, events = build_timeline(readings(spec), CFG)
        assert [e.type for e in events] == ["wicket"]  # 198 s later: not a DRS reversal
        wide = CFG.model_copy(update={"drs_window_s": 300.0})
        _, events = build_timeline(readings(spec), wide)
        assert [e.type for e in events] == ["wicket", "wicket_overturned"]


class TestNoScorebox:
    def test_empty_outputs(self, tmp_path: Path) -> None:
        paths = JobPaths("job", data_dir=tmp_path)
        paths.ensure_job_dir()
        write_model(paths.scorebox_json, Scorebox(found=False))
        ctx = PipelineContext(
            job_id="job", db_path=tmp_path / "db", paths=paths, config=load_config()
        )
        run_read_score(ctx)
        assert read_model(paths.score_readings_json, list[ScoreReading]) == []
        assert read_model(paths.score_events_json, list[ScoreEvent]) == []
        assert read_model(paths.score_timeline_json, list[ScoreTimelineEntry]) == []
        assert is_valid_read_score(ctx)
