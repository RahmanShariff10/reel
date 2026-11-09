"""Tests for slice-50-football-metrics.

Acceptance criteria:
- Goals identical to the labels give E1 precision and recall of 1.0.
- A goal 31 s from its label counts as both a miss and a false detection.
- Events covering 3 of 4 key actions give E2 of 0.75.
- A goal clip covering label -3 s to +3 s counts for E3; one starting at label -2 s doesn't.
- A fixed seed gives an identical E5 random baseline across runs.
- A reel with all clips containing key actions gives E5 of 1.0.
- summary.md lists each target as met, not met or n/a.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reel.common.models import (
    ClipBoundary,
    Event,
    Meta,
    ReelClip,
    ReelPlan,
    Scorebox,
    ScoreTimelineEntry,
    Summary,
    write_model,
)
from reel.common.paths import JobPaths

from eval import report
from eval.metrics import (
    e1_goals,
    e2_key_actions,
    e3_goal_clips,
    e5_reel_quality,
    goal_times,
    in_play_intervals,
    key_action_times,
)
from eval.soccernet import Label


def event(
    moment: float,
    type_: str = "goal",
    start: float | None = None,
    end: float | None = None,
    overturned: bool = False,
    id_: str = "ev-1",
) -> Event:
    return Event(
        id=id_,
        type=type_,
        importance=0.9,
        confidence=0.9,
        moment_s=moment,
        clip=ClipBoundary(
            start_s=moment - 20 if start is None else start,
            end_s=moment + 25 if end is None else end,
        ),
        overturned=overturned,
    )


def clip(start: float, end: float, event_id: str = "ev-1") -> ReelClip:
    return ReelClip(event_id=event_id, start_s=start, end_s=end, duration_s=end - start)


def label(half: int, seconds: float, name: str) -> Label:
    return Label(half=half, game_time="", position_ms=int(seconds * 1000), label=name)


class TestLabelTimes:
    def test_second_half_goals_are_shifted(self) -> None:
        labels = [label(2, 100.0, "Goal"), label(1, 50.0, "Goal"), label(1, 60.0, "Foul")]
        assert goal_times(labels, 2800.0) == [50.0, 2900.0]

    def test_only_key_actions(self) -> None:
        labels = [
            label(1, 10.0, "Shots on target"),
            label(1, 20.0, "Penalty"),
            label(1, 30.0, "Corner"),
            label(2, 5.0, "Red card"),
            label(2, 6.0, "Yellow->red card"),
            label(2, 7.0, "Yellow card"),
        ]
        assert key_action_times(labels, 100.0) == [10.0, 20.0, 105.0, 106.0]


class TestE1:
    def test_identical_goals(self) -> None:
        goals = [100.0, 2000.0, 4000.0]
        result = e1_goals([event(t) for t in goals], goals)
        assert result.precision == 1.0 and result.recall == 1.0

    def test_31_seconds_away_is_a_miss_and_a_false_detection(self) -> None:
        result = e1_goals([event(131.0)], [100.0])
        assert (result.tp, result.fp, result.fn) == (0, 1, 1)

    def test_30_seconds_away_counts(self) -> None:
        assert e1_goals([event(130.0)], [100.0]).tp == 1

    def test_one_label_cannot_match_two_goals(self) -> None:
        result = e1_goals([event(100.0), event(105.0)], [100.0])
        assert (result.tp, result.fp, result.fn) == (1, 1, 0)

    def test_overturned_goal_ignored(self) -> None:
        result = e1_goals([event(100.0, overturned=True)], [100.0])
        assert (result.tp, result.fp, result.fn) == (0, 0, 1)

    def test_other_types_ignored(self) -> None:
        assert e1_goals([event(100.0, "chance")], [100.0]).tp == 0

    def test_no_goals_at_all_is_undefined(self) -> None:
        result = e1_goals([], [])
        assert result.precision is None and result.recall is None


class TestE2:
    def test_three_of_four(self) -> None:
        actions = [100.0, 500.0, 900.0, 1300.0]
        events = [event(110.0, "goal"), event(505.0, "chance"), event(915.0, "penalty")]
        assert e2_key_actions(events, actions).ratio == 0.75

    def test_16_seconds_is_outside(self) -> None:
        assert e2_key_actions([event(116.0, "chance")], [100.0]).ratio == 0.0

    @pytest.mark.parametrize("type_", ["yellow_card", "moment"])
    def test_excluded_from_all_mode(self, type_: str) -> None:
        assert e2_key_actions([event(100.0, type_)], [100.0]).ratio == 0.0

    def test_moment_counts_without_score_graphic(self) -> None:
        assert e2_key_actions([event(100.0, "moment")], [100.0], scorebox_found=False).ratio == 1.0

    def test_overturned_excluded(self) -> None:
        assert e2_key_actions([event(100.0, overturned=True)], [100.0]).ratio == 0.0


class TestE3:
    def test_clip_covering_the_margin_counts(self) -> None:
        assert e3_goal_clips([event(100.0, start=97.0, end=103.0)], [100.0]).ratio == 1.0

    def test_clip_starting_two_seconds_before_does_not(self) -> None:
        assert e3_goal_clips([event(100.0, start=98.0, end=130.0)], [100.0]).ratio == 0.0

    def test_clip_ending_too_soon_does_not(self) -> None:
        assert e3_goal_clips([event(100.0, start=80.0, end=102.0)], [100.0]).ratio == 0.0

    def test_only_goal_clips_count(self) -> None:
        assert e3_goal_clips([event(100.0, "chance")], [100.0]).ratio == 0.0


class TestE5:
    INTERVALS = [(0.0, 3000.0), (3500.0, 6500.0)]

    def _plan(self, clips: list[ReelClip]) -> ReelPlan:
        return ReelPlan(mode="5min", duration_s=300.0, clips=clips)

    def test_all_clips_contain_actions(self) -> None:
        plan = self._plan([clip(90.0, 110.0), clip(490.0, 510.0)])
        result = e5_reel_quality(plan, [100.0, 500.0], self.INTERVALS)
        assert result.share == 1.0 and (result.clips, result.with_action) == (2, 2)

    def test_half_of_clips(self) -> None:
        plan = self._plan([clip(90.0, 110.0), clip(200.0, 220.0)])
        assert e5_reel_quality(plan, [100.0], self.INTERVALS).share == 0.5

    def test_fixed_seed_is_repeatable(self) -> None:
        plan = self._plan([clip(float(i) * 100, float(i) * 100 + 30) for i in range(10)])
        actions = [float(i) * 37 for i in range(100)]
        first = e5_reel_quality(plan, actions, self.INTERVALS, seed=7)
        second = e5_reel_quality(plan, actions, self.INTERVALS, seed=7)
        different = e5_reel_quality(plan, actions, self.INTERVALS, seed=8)
        assert first.random_share == second.random_share
        assert first.random_share != different.random_share

    def test_random_baseline_is_below_a_good_reel(self) -> None:
        actions = [float(i) * 300 + 10 for i in range(20)]
        plan = self._plan([clip(t - 10, t + 10) for t in actions[:10]])
        result = e5_reel_quality(plan, actions, self.INTERVALS)
        assert result.share == 1.0 and result.random_share < 0.3

    def test_empty_plan(self) -> None:
        assert e5_reel_quality(self._plan([]), [100.0], self.INTERVALS).share is None


class TestInPlayIntervals:
    def _entry(self, t: float, in_play: bool) -> ScoreTimelineEntry:
        return ScoreTimelineEntry(time_s=t, in_play=in_play)

    def test_halves(self) -> None:
        timeline = [
            self._entry(0, False),
            self._entry(10, True),
            self._entry(50, True),
            self._entry(60, False),
            self._entry(80, True),
            self._entry(100, True),
        ]
        assert in_play_intervals(timeline, 100.0) == [(10, 60), (80, 100)]

    def test_no_timeline_is_the_whole_video(self) -> None:
        assert in_play_intervals([], 500.0) == [(0.0, 500.0)]


def make_match(root: Path, game: str, job_id: str, *, good: bool = True, plan: bool = True) -> None:
    """A finished job plus labels: two goals at 100 s and 2900 s, and a shot at 500 s."""
    labels_dir = root / "labels" / game
    labels_dir.mkdir(parents=True)
    (labels_dir / "Labels-v2.json").write_text(
        json.dumps(
            {
                "annotations": [
                    {"gameTime": "1 - 01:40", "label": "Goal", "position": "100000"},
                    {"gameTime": "1 - 08:20", "label": "Shots on target", "position": "500000"},
                    {"gameTime": "2 - 01:40", "label": "Goal", "position": "100000"},
                ]
            }
        )
    )
    prepared = root / "prepared" / game
    prepared.mkdir(parents=True)
    (prepared / "match.json").write_text(json.dumps({"first_half_s": 2800.0}))

    paths = JobPaths(job_id, data_dir=root / "data")
    paths.ensure_job_dir()
    moments = [100.0, 2900.0] if good else [1000.0]
    events = [event(m, id_=f"ev-{i}") for i, m in enumerate(moments)]
    if good:
        events.append(event(500.0, "chance", id_="ev-9"))
    write_model(paths.events_json, events)
    write_model(paths.scorebox_json, Scorebox(found=good))
    write_model(paths.meta_json, Meta(duration_s=6000.0, width=1280, height=720, fps=25.0))
    write_model(paths.summary_json, Summary(processing_s=1800.0 if good else 4000.0))
    if plan:
        write_model(
            paths.reel_plan_path("5min"),
            ReelPlan(
                mode="5min",
                duration_s=100.0,
                clips=[clip(m - 10, m + 10, f"ev-{i}") for i, m in enumerate(moments)],
            ),
        )


def write_manifest(root: Path, rows: list[str]) -> Path:
    path = root / "manifest.yaml"
    path.write_text("matches:\n" + "".join(rows))
    return path


def run_report(root: Path, manifest: Path, split: str = "test") -> str:
    assert (
        report.main(
            [
                "--manifest",
                str(manifest),
                "--split",
                split,
                "--data-dir",
                str(root / "data"),
                "--labels",
                str(root / "labels"),
                "--prepared",
                str(root / "prepared"),
                "--out-dir",
                str(root / "out"),
            ]
        )
        == 0
    )
    return (root / "out" / "summary.md").read_text()


def entry(game: str, job_id: str | None = None, split: str = "test") -> str:
    job = f"    job_id: {job_id}\n" if job_id else ""
    return f"  - game: {game}\n    split: {split}\n    commentary_language: en\n{job}"


def row(text: str, metric: str) -> list[str]:
    line = next(ln for ln in text.splitlines() if ln.startswith(f"| {metric}"))
    return [cell.strip() for cell in line.strip("|").split("|")]


class TestReport:
    def test_every_target_marked(self, tmp_path: Path) -> None:
        make_match(tmp_path, "l/s/Good", "job-good")
        text = run_report(tmp_path, write_manifest(tmp_path, [entry("l/s/Good", "job-good")]))
        for metric in report.TARGETS:
            assert row(text, metric)[-1] == "met", metric

    def test_not_met_and_na(self, tmp_path: Path) -> None:
        make_match(tmp_path, "l/s/Bad", "job-bad", good=False, plan=False)
        text = run_report(tmp_path, write_manifest(tmp_path, [entry("l/s/Bad", "job-bad")]))
        assert row(text, report.GOAL_RECALL)[-1] == "not met"
        assert row(text, report.SCORE_FOUND)[-1] == "not met"
        assert row(text, report.PROCESSING)[-1] == "not met"
        assert row(text, report.REEL_QUALITY)[-1] == "n/a"

    def test_counts_are_pooled_across_matches(self, tmp_path: Path) -> None:
        make_match(tmp_path, "l/s/Good", "job-good")
        make_match(tmp_path, "l/s/Bad", "job-bad", good=False)
        text = run_report(
            tmp_path,
            write_manifest(tmp_path, [entry("l/s/Good", "job-good"), entry("l/s/Bad", "job-bad")]),
        )
        cells = row(text, report.GOAL_RECALL)
        assert cells[2:4] == ["1.000", "0.000"]
        assert cells[-2] == "0.500"
        assert row(text, report.PROCESSING)[-2] == "4000"

    def test_entries_without_a_job_are_listed(self, tmp_path: Path) -> None:
        make_match(tmp_path, "l/s/Good", "job-good")
        text = run_report(
            tmp_path,
            write_manifest(tmp_path, [entry("l/s/Good", "job-good"), entry("l/s/Pending")]),
        )
        assert "## Not evaluated (no job_id)" in text and "- Pending" in text

    def test_split_filter(self, tmp_path: Path) -> None:
        make_match(tmp_path, "l/s/Good", "job-good")
        manifest = write_manifest(tmp_path, [entry("l/s/Good", "job-good", split="dev")])
        assert "0 match(es) evaluated" in run_report(tmp_path, manifest)
        assert "1 match(es) evaluated" in run_report(tmp_path, manifest, split="dev")

    def test_no_matches_gives_na(self, tmp_path: Path) -> None:
        text = run_report(tmp_path, write_manifest(tmp_path, [entry("l/s/Pending")]))
        for metric in report.TARGETS:
            assert row(text, metric)[-1] == "n/a", metric

    def test_deterministic_and_numbers_only(self, tmp_path: Path) -> None:
        make_match(tmp_path, "l/s/Good", "job-good")
        manifest = write_manifest(tmp_path, [entry("l/s/Good", "job-good")])
        first = run_report(tmp_path, manifest)
        assert first == run_report(tmp_path, manifest)
        for forbidden in ("![", "<img", ".jpg", ".png", ".mp4"):
            assert forbidden not in first
