"""Tests for slice-11-score-read.

Acceptance criteria:
- Parser: "IND 145/3 16.2", "145-3", "3/145" (wickets-runs), "16.2 ov", "OVERS 16.2" and
  garbage each parse correctly or return "no reading".
- Synthetic video: >= 98% of crops in visible periods parse to the schedule's values.
- Scheduled hidden-box intervals: >= 95% of crops inside them are visible: false.
- OCR runs on fewer than 25% of crops (unchanged crops are skipped).
"""

from __future__ import annotations

import re

import numpy as np
import pytest

from reel.common.config import ScoreboardConfig
from reel.common.models import Scorebox, read_model
from reel.jobs.pipeline import PipelineContext
from reel.scoreboard.parse import ParsedScore, parse_score
from reel.scoreboard.read import crop_changed, read_crops
from tests.conftest import SyntheticMatch
from tests.fixtures.make_synthetic import score_text_at

EDGE_S = 0.1  # crops this close to a scheduled change can show either side (one frame)


class TestParser:
    @pytest.mark.parametrize("text,order,expected", [
        ("IND 145/3 16.2", "runs-wickets", ParsedScore("IND", 145, 3, 16.2)),
        ("145-3", "runs-wickets", ParsedScore(None, 145, 3, None)),
        ("AUS 3/145", "wickets-runs", ParsedScore("AUS", 145, 3, None)),
        ("16.2 ov", "runs-wickets", ParsedScore(None, None, None, 16.2)),
        ("OVERS 16.2", "runs-wickets", ParsedScore(None, None, None, 16.2)),
        ("IND 145/215.3", "runs-wickets", ParsedScore("IND", 145, 2, 15.3)),
    ])
    def test_parses(self, text: str, order: str, expected: ParsedScore) -> None:
        assert parse_score(text, order) == expected

    @pytest.mark.parametrize("text", ["", "PLAYER OF THE MATCH", "RR 8.25", "145/45"])
    def test_garbage_is_no_reading(self, text: str) -> None:
        parsed = parse_score(text)
        assert parsed is None or parsed.runs is None


class TestChangeDetection:
    def test_noise_ignored_digit_change_detected(self) -> None:
        cfg = ScoreboardConfig()
        a = np.zeros((50, 300, 3), np.uint8)
        noisy = a + np.random.default_rng(0).integers(0, 8, a.shape, dtype=np.uint8)
        assert not crop_changed(a, noisy, cfg)
        digit = a.copy()
        digit[15:35, 100:112] = 255  # one digit-sized change
        assert crop_changed(a, digit, cfg)


@pytest.fixture(scope="module")
def readings(scanned_match: PipelineContext):
    order = read_model(scanned_match.paths.scorebox_json, Scorebox).order
    crops = list(scanned_match.paths.score_crops_dir.glob("crop_*.png"))
    return read_crops(crops, order, scanned_match.config.scoreboard)


def _near_boundary(schedule: dict, t: float) -> bool:
    edges = [c["time_s"] for c in schedule["score_changes"]]
    edges += [e for h in schedule["hidden_intervals"] for e in h]
    return any(abs(t - e) <= EDGE_S for e in edges)


class TestSyntheticReading:
    def test_visible_crops_parse_correctly(self, readings, synthetic_match: SyntheticMatch):
        rd, _ = readings
        s = synthetic_match.schedule
        total = ok = 0
        for r in rd:
            expected = score_text_at(s, r.time_s)
            if expected is None or _near_boundary(s, r.time_s):
                continue
            team, runs, wkts, overs = re.match(r"(\w+) (\d+)/(\d+)\s+(\d+\.\d)", expected).groups()
            total += 1
            ok += r.visible and (r.team, r.runs, r.wickets, r.overs) == (
                team, int(runs), int(wkts), float(overs))
        assert total > 100 and ok / total >= 0.98

    def test_hidden_crops_marked_invisible(self, readings, synthetic_match: SyntheticMatch):
        rd, _ = readings
        s = synthetic_match.schedule
        hidden = [r for r in rd
                  if score_text_at(s, r.time_s) is None and not _near_boundary(s, r.time_s)]
        assert hidden and sum(not r.visible for r in hidden) / len(hidden) >= 0.95

    def test_ocr_runs_on_few_crops(self, readings) -> None:
        _, stats = readings
        assert stats.ocr_calls / stats.crops < 0.25


class TestJobOutput:
    def test_writes_score_readings_json(self, scanned_match: PipelineContext) -> None:
        from reel.common.models import ScoreReading
        from reel.scoreboard.read import read_job_crops

        readings = read_job_crops(scanned_match)
        stored = read_model(scanned_match.paths.score_readings_json, list[ScoreReading])
        assert stored == readings and len(stored) > 200
