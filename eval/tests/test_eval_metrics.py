"""Tests for slice-25-eval-metrics.

Acceptance criteria:
- A job where every delivery matches Cricsheet gives E2 recall = precision = 1.0.
- A clip starting 2 s after the annotated t_start_s does not contain the moment, and the
  offset is reported as +2 s.
- Several matches: the report aggregates per match and overall and marks each metric
  met / not met against the PRD targets.
- The same inputs give an identical report.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from reel.common.models import ClipBoundary, Delivery, Event, Summary, write_model
from reel.common.paths import JobPaths

from eval import report
from eval.annotations import Annotation
from eval.cricsheet import Ball, load_balls
from eval.metrics import e2_deliveries, e3_clips
from eval.tests.test_eval_foundation import FIXTURE, events_from_truth


def perfect_deliveries(balls: list[Ball]) -> list[Delivery]:
    return [
        Delivery(
            id=f"d{i}",
            innings=b.innings,
            over_ball=b.score_overs_after,
            start_s=i * 30.0,
            t_hit_s=i * 30.0 + 5,
            end_s=i * 30.0 + 30,
        )
        for i, b in enumerate(balls)
    ]


def event(type_: str, start: float, end: float, over: str = "4.3", moment: float = 100.0):
    return Event(
        id="ev-001",
        type=type_,
        innings=1,
        over_ball=over,
        importance=0.9,
        confidence=0.9,
        moment_s=moment,
        clip=ClipBoundary(start_s=start, end_s=end),
    )


ANN = Annotation("m", 1, "4.3", "six", t_start_s=94.0, t_moment_s=100.0)


class TestE2:
    def test_perfect_match(self) -> None:
        balls = load_balls(FIXTURE)
        r = e2_deliveries(perfect_deliveries(balls), balls)
        assert (r.recall, r.precision, r.gap) == (1.0, 1.0, 0)

    def test_missing_and_extra(self) -> None:
        balls = load_balls(FIXTURE)
        ds = perfect_deliveries(balls)[2:]  # two missed
        r = e2_deliveries(ds, balls)
        assert r.gap == -2 and r.precision == 1.0 and r.recall == (len(balls) - 2) / len(balls)


class TestE3:
    def test_late_clip_not_contained(self) -> None:
        r = e3_clips([ANN], [event("six", start=96.0, end=115.0)])
        assert r.contained == 0 and r.offsets == [2.0] and r.median_offset == 2.0

    def test_good_clip_contained(self) -> None:
        r = e3_clips([ANN], [event("six", start=93.0, end=104.0)])
        assert r.contained == 1 and r.contained_ratio == 1.0

    def test_short_clip_and_missing_event(self) -> None:
        r = e3_clips(
            [ANN, Annotation("m", 1, "9.1", "four", 300.0, 305.0)],
            [event("six", start=93.0, end=101.0)],
        )  # ends < moment + 3 s
        assert r.total == 2 and r.contained == 0 and r.missing == ["1:9.1 four"]


def build_job(data_dir: Path, job_id: str, drop_six: int | None = None) -> None:
    balls = load_balls(FIXTURE)
    paths = JobPaths(job_id, data_dir=data_dir)
    write_model(paths.score_events_json, events_from_truth(balls, drop_six=drop_six))
    write_model(paths.deliveries_json, perfect_deliveries(balls))
    write_model(paths.events_json, [event("six", 93.0, 104.0)])
    write_model(paths.summary_json, Summary(processing_s=1800.0))


def write_manifest(tmp: Path) -> Path:
    ann_file = tmp / "m.csv"
    ann_file.write_text(
        "match_id,innings,over_ball,type,t_start_s,t_moment_s\nm,1,4.3,six,94.0,100.0\n"
    )
    manifest = tmp / "matches.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {
                "matches": [
                    {
                        "match_id": "m1",
                        "job_id": "j1",
                        "cricsheet": str(FIXTURE),
                        "annotations": str(ann_file),
                    },
                    {
                        "match_id": "m2",
                        "job_id": "j2",
                        "cricsheet": str(FIXTURE),
                        "annotations": str(ann_file),
                    },
                ]
            }
        )
    )
    return manifest


class TestReport:
    def test_aggregates_and_marks_targets(self, tmp_path: Path) -> None:
        build_job(tmp_path / "data", "j1")
        build_job(tmp_path / "data", "j2", drop_six=1)
        out = tmp_path / "reports"
        args = [
            "--manifest",
            str(write_manifest(tmp_path)),
            "--data-dir",
            str(tmp_path / "data"),
            "--out-dir",
            str(out),
        ]
        assert report.main(args) == 0
        md = (out / "summary.md").read_text()
        assert "| Metric | Target | m1 | m2 | Overall | Result |" in md
        e1_row = next(line for line in md.splitlines() if line.startswith("| E1 recall"))
        assert "| 1.000 |" in e1_row and e1_row.endswith("met |")
        assert "| Processing time (s) | <= 3600 | 1800 | 1800 | 1800 | met |" in md
        assert (out / "summary.csv").read_text().startswith("Metric,Target,m1,m2,Overall,Result")

    def test_deterministic(self, tmp_path: Path) -> None:
        build_job(tmp_path / "data", "j1")
        build_job(tmp_path / "data", "j2")
        manifest = write_manifest(tmp_path)
        texts = []
        for run in range(2):
            out = tmp_path / f"r{run}"
            report.main(
                [
                    "--manifest",
                    str(manifest),
                    "--data-dir",
                    str(tmp_path / "data"),
                    "--out-dir",
                    str(out),
                ]
            )
            texts.append((out / "summary.md").read_text() + (out / "summary.csv").read_text())
        assert texts[0] == texts[1]
