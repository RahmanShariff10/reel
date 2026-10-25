"""Tests for slice-13-eval-foundation.

Acceptance criteria:
- The loader returns the correct number of fours, sixes and wickets per innings.
- 4 leg-byes count as a four; a wide keeps over.ball numbering correct.
- The annotation validator reports the line and problem for a missing column / bad over.
- Predictions identical to the ground truth give precision = recall = 1.0 for every type.
- Predictions missing one of n sixes give six recall (n-1)/n.
- Report files are written to eval/reports/<match_id>/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from reel.common.models import ScoreEvent, write_model
from reel.common.paths import JobPaths

from eval import annotations, e1
from eval.cricsheet import Ball, counts, load_balls

FIXTURE = Path(__file__).parent / "fixtures" / "sample_t20.json"


@pytest.fixture(scope="module")
def balls() -> list[Ball]:
    return load_balls(FIXTURE)


def events_from_truth(balls: list[Ball], drop_six: int | None = None) -> list[ScoreEvent]:
    """Build score events that a perfect pipeline would emit for these balls."""
    events, t, six_seen = [], 0.0, 0
    for b in balls:
        t += 30.0
        overs = float(b.score_overs_after)
        if b.type == "wicket":
            events.append(
                ScoreEvent(type="wicket", time_s=t, wicket_delta=1, overs=overs, innings=b.innings)
            )
        elif b.type in ("four", "six"):
            if b.type == "six":
                six_seen += 1
                if six_seen == drop_six:
                    continue
            events.append(
                ScoreEvent(
                    type="runs",
                    time_s=t,
                    runs_delta=4 if b.type == "four" else 6,
                    overs=overs,
                    innings=b.innings,
                )
            )
    return events


class TestCricsheetLoader:
    def test_counts_per_innings(self, balls: list[Ball]) -> None:
        assert counts(balls) == {
            1: {"four": 3, "six": 2, "wicket": 1},  # retired hurt is not a wicket
            2: {"four": 1, "six": 1, "wicket": 1},
        }

    def test_leg_byes_four_and_wide_numbering(self, balls: list[Ball]) -> None:
        first_over = [b for b in balls if b.innings == 1 and b.over == 0]
        assert [b.over_ball for b in first_over] == [
            "0.1",
            "0.2",
            "0.2",
            "0.3",
            "0.4",
            "0.5",
            "0.6",
        ]
        wide = first_over[1]
        assert not wide.legal and wide.score_overs_after == "0.1"
        assert first_over[5].type == "four"  # 4 leg-byes
        assert first_over[6].score_overs_after == "1.0"

    def test_no_ball_four_counts(self, balls: list[Ball]) -> None:
        nb = [b for b in balls if b.innings == 1 and b.over == 1][2]
        assert not nb.legal and nb.type == "four" and nb.total_runs == 5


class TestAnnotations:
    def _write(self, tmp_path: Path, text: str) -> Path:
        p = tmp_path / "m.csv"
        p.write_text(text)
        return p

    def test_valid_file(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            "match_id,innings,over_ball,type,t_start_s,t_moment_s\nm1,1,4.3,wicket,812.0,818.5\n",
        )
        assert annotations.validate(p) == []
        assert annotations.load(p)[0].over_ball == "4.3"

    def test_missing_column(self, tmp_path: Path) -> None:
        p = self._write(tmp_path, "match_id,innings,over_ball,type,t_start_s\nm1,1,4.3,six,1\n")
        assert annotations.validate(p) == ["line 1: missing column(s): t_moment_s"]

    def test_bad_over_format_reports_line(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            "match_id,innings,over_ball,type,t_start_s,t_moment_s\n"
            "m1,1,4.3,six,10,12\nm1,1,4-3,four,20,25\n",
        )
        problems = annotations.validate(p)
        assert (
            len(problems) == 1 and problems[0].startswith("line 3:") and "over_ball" in problems[0]
        )

    def test_cli_exit_code(self, tmp_path: Path) -> None:
        good = self._write(tmp_path, "match_id,innings,over_ball,type,t_start_s,t_moment_s\n")
        assert annotations.main([str(good)]) == 0


class TestE1:
    def test_perfect_predictions(self, balls: list[Ball]) -> None:
        scores = e1.score(e1.detected_events(events_from_truth(balls)), balls)
        for t in e1.TYPES:
            assert scores[t].precision == 1.0 and scores[t].recall == 1.0

    def test_missing_one_six(self, balls: list[Ball]) -> None:
        n = sum(b.type == "six" for b in balls)
        scores = e1.score(e1.detected_events(events_from_truth(balls, drop_six=1)), balls)
        assert scores["six"].recall == pytest.approx((n - 1) / n)
        assert scores["six"].precision == 1.0

    def test_overturned_wicket_is_not_counted(self) -> None:
        events = [
            ScoreEvent(type="wicket", time_s=10, wicket_delta=1, overs=0.4, innings=1),
            ScoreEvent(type="wicket_overturned", time_s=40, wicket_delta=-1, overs=0.4, innings=1),
        ]
        assert e1.detected_events(events) == []

    def test_cli_writes_reports(self, balls: list[Ball], tmp_path: Path) -> None:
        paths = JobPaths("job1", data_dir=tmp_path / "data")
        write_model(paths.score_events_json, events_from_truth(balls))
        out = tmp_path / "reports"
        assert (
            e1.main(
                [
                    "--job",
                    "job1",
                    "--cricsheet",
                    str(FIXTURE),
                    "--data-dir",
                    str(tmp_path / "data"),
                    "--out-dir",
                    str(out),
                ]
            )
            == 0
        )
        report = json.loads((out / "sample_t20" / "e1.json").read_text())
        assert report["types"]["wicket"]["recall"] == 1.0
        assert (out / "sample_t20" / "e1.md").read_text().startswith("# E1")
