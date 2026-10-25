"""Tests for slice-17-deliveries.

Acceptance criteria:
- Synthetic stage files: >= 95% of scheduled deliveries found, no replay counted as one.
- Every score event is assigned to the correct scheduled delivery.
- replay_count matches the schedule for every delivery.
- scorebox found: false → deliveries from run-up shots only, empty outcomes, stage succeeds.
- With a readable score timeline, over_ball is populated.

Shot labels come from the ground-truth schedule (a stand-in for a perfect classifier):
synthetic colour blocks are not meaningful to CLIP.
"""

from __future__ import annotations

import pytest

from reel.audio.excitement import run_audio
from reel.common.models import Delivery, Scorebox, Shot, read_model, write_model
from reel.deliveries.segment import is_valid_deliveries, run_deliveries
from reel.jobs.pipeline import PipelineContext
from reel.scoreboard.score_stage import run_read_score
from tests.conftest import SyntheticMatch


def label_from_schedule(ctx: PipelineContext, schedule: dict) -> None:
    shots = read_model(ctx.paths.shots_json, list[Shot])
    truth = schedule["shots"]
    labelled = []
    for s in shots:
        mid = (s.start_s + s.end_s) / 2
        scene = next(t for t in truth if t["start_s"] <= mid < t["end_s"])["scene"]
        labelled.append(s.model_copy(update={"label": scene, "label_source": "classifier"}))
    write_model(ctx.paths.shots_json, labelled)


@pytest.fixture(scope="module")
def deliveries(scanned_match: PipelineContext, synthetic_match: SyntheticMatch) -> list[Delivery]:
    ctx = scanned_match
    run_read_score(ctx)
    label_from_schedule(ctx, synthetic_match.schedule)
    cfg = ctx.config.model_copy(deep=True)
    cfg.audio.use_panns = False
    run_audio(PipelineContext(job_id="job", db_path=ctx.db_path, paths=ctx.paths, config=cfg))
    run_deliveries(ctx)
    assert is_valid_deliveries(ctx)
    return read_model(ctx.paths.deliveries_json, list[Delivery])


def match(deliveries: list[Delivery], start: float) -> Delivery | None:
    return next((d for d in deliveries if abs(d.start_s - start) <= 0.5), None)


class TestSynthetic:
    def test_deliveries_found_no_replays(self, deliveries, synthetic_match) -> None:
        truth = synthetic_match.schedule["deliveries"]
        found = [t for t in truth if match(deliveries, t["start_s"])]
        assert len(found) / len(truth) >= 0.95
        assert len(deliveries) == len(truth)  # replays did not become deliveries

    def test_outcomes_on_correct_delivery(self, deliveries, synthetic_match) -> None:
        expected = {
            "single": (1, False),
            "four": (4, False),
            "six": (6, False),
            "dot": (0, False),
            "wicket": (0, True),
            "wicket_drs": (0, True),
        }
        for t in synthetic_match.schedule["deliveries"]:
            d = match(deliveries, t["start_s"])
            assert d is not None, t
            assert (d.runs_delta, d.wicket) == expected[t["outcome"]], (t, d)
            assert d.overturned == (t["outcome"] == "wicket_drs")

    def test_replay_counts(self, deliveries, synthetic_match) -> None:
        for t in synthetic_match.schedule["deliveries"]:
            assert match(deliveries, t["start_s"]).replay_count == t["replay_count"], t

    def test_over_ball_and_score(self, deliveries, synthetic_match) -> None:
        for t in synthetic_match.schedule["deliveries"]:
            d = match(deliveries, t["start_s"])
            assert d.over_ball == t["over_ball"] and d.innings == t["innings"]
            assert d.score_after and d.score_after.split()[0] in ("IND", "AUS")

    def test_timing_and_excitement(self, deliveries) -> None:
        for a, b in zip(deliveries, deliveries[1:]):
            assert a.start_s < a.t_hit_s <= a.end_s == b.start_s
        big = [d for d in deliveries if d.runs_delta >= 4 or d.wicket]
        quiet = [d for d in deliveries if d.runs_delta < 4 and not d.wicket]
        assert min(d.excitement_max for d in big) > max(d.excitement_max for d in quiet)


class TestNoScorebox:
    def test_run_ups_only(self, scanned_match: PipelineContext, deliveries) -> None:
        paths = scanned_match.paths
        original = paths.scorebox_json.read_bytes()
        try:
            write_model(paths.scorebox_json, Scorebox(found=False))
            run_deliveries(scanned_match)
            got = read_model(paths.deliveries_json, list[Delivery])
        finally:
            paths.scorebox_json.write_bytes(original)
        shots = read_model(paths.shots_json, list[Shot])
        run_up_starts = {s.start_s for s in shots if s.label == "run_up"}
        assert got and all(d.start_s in run_up_starts for d in got)
        assert all(d.runs_delta == 0 and not d.wicket and d.over_ball is None for d in got)
