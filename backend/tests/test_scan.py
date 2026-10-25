"""Tests for slice-09-scan-pass.

Acceptance criteria:
- Synthetic video: every scheduled cut detected within ±0.5 s, precision and recall >= 95%.
- Each shot has exactly one keyframe, taken from inside that shot.
- Found score box: duration x 2 (±1) crops, each with the box's dimensions, filenames
  encoding their timestamp.
- found: false → no crops and the stage succeeds.
- Exactly one ffmpeg process reads the full input.
- Job progress updates at least every 30 s during a long scan.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from reel.common.config import load_config
from reel.common.models import Scorebox, Shot, read_model
from reel.common.paths import JobPaths
from reel.ingest import scan as scan_module
from reel.ingest.scan import crop_time, is_valid_scan, run_scan
from reel.ingest.stage import run_ingest
from reel.jobs.pipeline import PipelineContext
from reel.scoreboard.stage import run_locate_scorebox
from tests.conftest import SyntheticMatch, make_synthetic_match
from tests.fixtures.make_synthetic import SCENE_COLOURS


def prepare(video: Path, tmp: Path) -> PipelineContext:
    paths = JobPaths("job", data_dir=tmp)
    paths.ensure_job_dir()
    ctx = PipelineContext(job_id="job", db_path=tmp / "reel.db", paths=paths,
                          config=load_config(), input_path=video)
    run_ingest(ctx)
    run_locate_scorebox(ctx)
    return ctx


@pytest.fixture(scope="module")
def scanned(synthetic_match: SyntheticMatch, tmp_path_factory) -> PipelineContext:
    ctx = prepare(synthetic_match.video, tmp_path_factory.mktemp("scan"))
    calls: list[float] = []
    run_scan(ctx, calls.append)
    ctx.progress_calls = calls  # type: ignore[attr-defined]
    return ctx


def hex_to_bgr(h: str) -> np.ndarray:
    v = int(h, 16)
    return np.array([v & 255, (v >> 8) & 255, v >> 16], dtype=float)


class TestCuts:
    def test_cuts_within_half_second(self, scanned, synthetic_match: SyntheticMatch) -> None:
        shots = read_model(scanned.paths.shots_json, list[Shot])
        detected = [s.start_s for s in shots[1:]]
        truth = synthetic_match.schedule["cuts"]
        hits = [t for t in truth if any(abs(t - d) <= 0.5 for d in detected)]
        good = [d for d in detected if any(abs(t - d) <= 0.5 for t in truth)]
        assert len(hits) / len(truth) >= 0.95
        assert len(good) / len(detected) >= 0.95

    def test_shots_cover_video(self, scanned, synthetic_match: SyntheticMatch) -> None:
        shots = read_model(scanned.paths.shots_json, list[Shot])
        assert shots[0].start_s == 0.0
        assert shots[-1].end_s == pytest.approx(synthetic_match.schedule["duration_s"], abs=0.1)
        for a, b in zip(shots, shots[1:]):
            assert a.end_s == b.start_s


class TestKeyframes:
    def test_one_keyframe_per_shot_from_inside_it(self, scanned, synthetic_match) -> None:
        shots = read_model(scanned.paths.shots_json, list[Shot])
        files = sorted(scanned.paths.keyframes_dir.glob("*.jpg"))
        assert len(files) == len(shots)
        truth = synthetic_match.schedule["shots"]
        for shot in shots:
            img = cv2.imread(str(scanned.paths.root / shot.keyframe_path))
            assert img is not None
            mid = (shot.start_s + shot.end_s) / 2
            scene = next(t for t in truth if t["start_s"] <= mid < t["end_s"])["scene"]
            h, w = img.shape[:2]
            colour = img[int(h * 0.4), int(w * 0.1)].astype(float)  # background, off the pitch
            assert np.abs(colour - hex_to_bgr(SCENE_COLOURS[scene])).max() < 40, shot


class TestScoreCrops:
    def test_crop_count_size_and_names(self, scanned, synthetic_match: SyntheticMatch) -> None:
        box = read_model(scanned.paths.scorebox_json, Scorebox).box
        crops = sorted(scanned.paths.score_crops_dir.glob("crop_*.png"))
        assert abs(len(crops) - synthetic_match.schedule["duration_s"] * 2) <= 1
        times = [crop_time(c) for c in crops]
        assert times == sorted(times) and times[0] == 0.0 and times[1] == 0.5
        for c in crops[::40]:
            img = cv2.imread(str(c))
            assert (img.shape[1], img.shape[0]) == (box[2], box[3])

    def test_no_scorebox_no_crops(self, tmp_path: Path) -> None:
        m = make_synthetic_match(tmp_path / "nsb", duration_s=20.0, scorebox=False)
        ctx = prepare(m.video, tmp_path / "job")
        run_scan(ctx)
        assert list(ctx.paths.score_crops_dir.iterdir()) == []
        assert is_valid_scan(ctx)


class TestSingleDecode:
    def test_one_ffmpeg_process(self, synthetic_match, tmp_path: Path, monkeypatch) -> None:
        ctx = prepare(synthetic_match.video, tmp_path)
        launched: list[list[str]] = []
        real_popen = subprocess.Popen

        def counting_popen(cmd, *args, **kwargs):
            launched.append(cmd)
            return real_popen(cmd, *args, **kwargs)

        def no_run(*args, **kwargs):
            raise AssertionError("scan must not start other processes")

        monkeypatch.setattr(scan_module.subprocess, "Popen", counting_popen)
        monkeypatch.setattr(scan_module.subprocess, "run", no_run)
        run_scan(ctx)
        assert len(launched) == 1 and "ffmpeg" in Path(launched[0][0]).name


class TestProgress:
    def test_progress_reported_regularly(self, scanned, synthetic_match) -> None:
        # one update per 100 low-res frames = every 25 s of video at 4 fps
        frames = synthetic_match.schedule["duration_s"] * 4
        calls = scanned.progress_calls
        assert len(calls) >= int(frames // 100)
        assert calls == sorted(calls) and calls[-1] == 1.0
