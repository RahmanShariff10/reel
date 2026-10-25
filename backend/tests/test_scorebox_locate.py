"""Tests for slice-08-scorebox-locate.

Acceptance criteria:
- Synthetic video: box found with IoU >= 0.7 against the true rectangle, and the sample
  reading matches the schedule at that time.
- --order wickets-runs video: stored order is "wickets-runs".
- --distractor video: the static number graphic is not chosen.
- --no-scorebox video: found false, scorebox_preview.jpg still exists, the job continues.
- Threshold changes in config change behaviour with no code change.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from reel.common.config import ReelConfig, ScoreboardConfig, load_config
from reel.common.models import Scorebox, read_model
from reel.common.paths import JobPaths
from reel.ingest.stage import is_valid_ingest, run_ingest
from reel.jobs.pipeline import PipelineContext, Stage, run_pipeline
from reel.jobs.store import claim_next_job, create_job, get_job, init_db
from reel.scoreboard.locate import infer_order, plausibility, sample_times
from reel.scoreboard.parse import ScorePair, find_overs, find_pair
from reel.scoreboard.stage import is_valid_locate_scorebox, run_locate_scorebox
from tests.conftest import SyntheticMatch, make_synthetic_match
from tests.fixtures.make_synthetic import score_text_at


def iou(a: list[int], b: list[int]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    return inter / (aw * ah + bw * bh - inter)


def run_locate(
    video: Path, tmp: Path, config: ReelConfig | None = None
) -> tuple[Scorebox, JobPaths]:
    paths = JobPaths("job", data_dir=tmp)
    paths.ensure_job_dir()
    ctx = PipelineContext(job_id="job", db_path=tmp / "reel.db", paths=paths,
                          config=config or load_config(), input_path=video)
    run_ingest(ctx)
    run_locate_scorebox(ctx)
    return read_model(paths.scorebox_json, Scorebox), paths


@pytest.fixture(scope="module")
def variants(tmp_path_factory: pytest.TempPathFactory) -> dict[str, SyntheticMatch]:
    base = tmp_path_factory.mktemp("locate_variants")
    return {
        "wickets_runs": make_synthetic_match(base / "wr", duration_s=30.0, order="wickets-runs"),
        "distractor": make_synthetic_match(base / "dis", duration_s=30.0, distractor=True),
        "no_scorebox": make_synthetic_match(base / "nsb", duration_s=20.0, scorebox=False),
    }


class TestParse:
    @pytest.mark.parametrize("text,pair", [
        ("IND 145/3 16.2", (145, 3)), ("145-3", (145, 3)), ("AUS 3/145", (3, 145)),
        ("RR 8.25", None), ("no score", None),
        ("IND 145/215.3", (145, 2)), ("IND 145/1015.3", (145, 10)),
    ])
    def test_find_pair(self, text: str, pair: tuple[int, int] | None) -> None:
        got = find_pair(text)
        assert (got.first, got.second) == pair if pair else got is None

    @pytest.mark.parametrize("text,overs", [
        ("IND 145/3 16.2", 16.2), ("16.2 ov", 16.2), ("OVERS 0.5", 0.5),
        ("RR 8.25", None), ("IND 145/3", None), ("IND 145/215.3", 15.3),
    ])
    def test_find_overs(self, text: str, overs: float | None) -> None:
        assert find_overs(text) == overs


class TestValidationRules:
    def test_order_by_value_over_ten(self) -> None:
        assert infer_order([ScorePair(140, 2), ScorePair(145, 2)]) == "runs-wickets"
        assert infer_order([ScorePair(2, 140), ScorePair(2, 145)]) == "wickets-runs"
        assert infer_order([ScorePair(140, 20)]) is None

    def test_order_by_growth_when_both_small(self) -> None:
        assert infer_order([ScorePair(0, 0), ScorePair(0, 4), ScorePair(1, 10)]) == "wickets-runs"

    def test_plausibility_allows_drs_and_new_innings(self) -> None:
        seq = [ScorePair(*p) for p in [(140, 2), (145, 3), (145, 2), (152, 2), (0, 0), (4, 0)]]
        assert plausibility(seq, "runs-wickets") == 1.0
        assert plausibility([ScorePair(140, 2), ScorePair(90, 5)], "runs-wickets") == 0.0

    def test_sample_times_long_and_short(self) -> None:
        cfg = ScoreboardConfig(sample_frames=10)
        long = sample_times(3600.0, cfg)
        assert len(long) == 10 and long[0] >= 300 and long[-1] <= 3300
        short = sample_times(100.0, cfg)
        assert short[0] >= 5.0 and short[-1] <= 95.0


class TestLocateSynthetic:
    def test_box_found_and_reading_matches(self, synthetic_match: SyntheticMatch,
                                           tmp_path: Path) -> None:
        sb, paths = run_locate(synthetic_match.video, tmp_path)
        s = synthetic_match.schedule
        assert sb.found and sb.box is not None
        assert iou(sb.box, s["scorebox_rect"]) >= 0.7
        assert sb.order == "runs-wickets"
        expected = score_text_at(s, sb.sample_time_s)
        assert expected is not None
        assert re.sub(r"\s+", "", sb.sample_reading) == re.sub(r"\s+", "", expected)
        assert paths.scorebox_preview_jpg.is_file()

    def test_wickets_runs_order(self, variants, tmp_path: Path) -> None:
        sb, _ = run_locate(variants["wickets_runs"].video, tmp_path)
        assert sb.found and sb.order == "wickets-runs"

    def test_distractor_not_chosen(self, variants, tmp_path: Path) -> None:
        m = variants["distractor"]
        sb, _ = run_locate(m.video, tmp_path)
        assert sb.found
        assert iou(sb.box, m.schedule["distractor_rect"]) == 0.0
        assert iou(sb.box, m.schedule["scorebox_rect"]) >= 0.7

    def test_threshold_from_config(self, synthetic_match: SyntheticMatch, tmp_path: Path) -> None:
        # The box is hidden during replays, so it is present in < 99% of samples.
        strict = load_config(overrides={"scoreboard": {"min_valid_ratio": 0.99}})
        sb, _ = run_locate(synthetic_match.video, tmp_path, strict)
        assert not sb.found


class TestNoScorebox:
    def test_not_found_preview_saved_and_job_continues(self, variants, tmp_path: Path) -> None:
        db = tmp_path / "reel.db"
        init_db(db)
        video = variants["no_scorebox"].video
        job = create_job(db, input_path=str(video))
        claim_next_job(db)
        paths = JobPaths(job.id, data_dir=tmp_path)
        ctx = PipelineContext(job_id=job.id, db_path=db, paths=paths, input_path=video)
        after: list[str] = []
        stages = [
            Stage("ingest", 1.0, is_valid_ingest, run_ingest),
            Stage("locate_scorebox", 1.0, is_valid_locate_scorebox, run_locate_scorebox),
            Stage("next", 1.0, lambda c: False, lambda c: after.append("ran")),
        ]
        run_pipeline(ctx, stages)

        sb = read_model(paths.scorebox_json, Scorebox)
        assert sb.found is False and sb.box is None
        assert paths.scorebox_preview_jpg.is_file()
        assert after == ["ran"]
        assert get_job(db, job.id).status == "done"
