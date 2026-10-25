"""Tests for slice-21-render-reel.

Acceptance criteria:
- The reel is the title followed by the clips in plan order; its duration is within
  ±0.5 s of the planned total.
- The output is H.264 yuv420p + AAC with the moov atom at the start.
- With known team names the title card shows them; otherwise "Match highlights".
- A re-render replaces the old reel only when the new one is complete.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest
from rapidocr_onnxruntime import RapidOCR

from reel.common.config import load_config
from reel.common.models import (
    Delivery,
    ReelClip,
    ReelPlan,
    Scorebox,
    Summary,
    read_model,
    write_model,
)
from reel.common.paths import JobPaths
from reel.ingest.probe import find_binary
from reel.ingest.stage import run_ingest
from reel.jobs.pipeline import PipelineContext
from reel.render import reel as reel_module
from reel.render.reel import is_valid_render, make_title, render_reel, run_render
from tests.conftest import SyntheticMatch

PLAN = ReelPlan(
    mode="5min",
    duration_s=3.0 + 6.0 + 5.0,
    clips=[
        ReelClip(
            event_id="ev-001",
            start_s=16.0,
            end_s=22.0,
            duration_s=6.0,
            caption="FOUR · 15.2 ov · IND 145/2",
            offset_s=3.0,
        ),
        ReelClip(
            event_id="ev-002",
            start_s=95.0,
            end_s=100.0,
            duration_s=5.0,
            caption="FOUR · 0.1 ov · AUS 4/0",
            offset_s=9.0,
        ),
    ],
)
DELIVERIES = [
    Delivery(id="d1", innings=1, over_ball="16.1", start_s=10, end_s=20, score_after="IND 152/3"),
    Delivery(id="d2", innings=2, over_ball="0.2", start_s=90, end_s=99, score_after="AUS 10/0"),
]


def probe(path: Path) -> dict:
    out = subprocess.run(
        [
            find_binary("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,pix_fmt",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def frame(path: Path, t: float) -> np.ndarray:
    out = subprocess.run(
        [
            find_binary("ffmpeg"),
            "-v",
            "error",
            "-ss",
            f"{t:.3f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return cv2.imdecode(np.frombuffer(out.stdout, np.uint8), cv2.IMREAD_COLOR)


def ocr_text(img: np.ndarray) -> str:
    result, _ = RapidOCR()(img)
    return " ".join(r[1] for r in result or [])


@pytest.fixture(scope="module")
def job(synthetic_match: SyntheticMatch, tmp_path_factory) -> PipelineContext:
    tmp = tmp_path_factory.mktemp("reel")
    paths = JobPaths("job", data_dir=tmp)
    paths.ensure_job_dir()
    ctx = PipelineContext(
        job_id="job",
        db_path=tmp / "db",
        paths=paths,
        config=load_config(),
        input_path=synthetic_match.video,
    )
    run_ingest(ctx)
    write_model(paths.scorebox_json, Scorebox(found=False))
    write_model(paths.reel_plan_path("5min"), PLAN)
    write_model(paths.deliveries_json, DELIVERIES)
    run_render(ctx)
    return ctx


class TestReel:
    def test_order_and_duration(self, job: PipelineContext, synthetic_match) -> None:
        out = job.paths.reel_path("5min")
        assert abs(float(probe(out)["format"]["duration"]) - PLAN.duration_s) <= 0.5
        title = frame(out, 1.5)
        assert np.abs(title[5, 5].astype(int) - (42, 27, 13)).max() < 20  # navy background
        for clip in PLAN.clips:
            ours = frame(out, clip.offset_s + clip.duration_s / 2)
            src = frame(synthetic_match.video, clip.start_s + clip.duration_s / 2)
            assert np.abs(ours[100, 640].astype(int) - src[100, 640].astype(int)).max() < 25

    def test_format_and_faststart(self, job: PipelineContext) -> None:
        out = job.paths.reel_path("5min")
        streams = {s["codec_type"]: s for s in probe(out)["streams"]}
        assert streams["video"]["codec_name"] == "h264"
        assert streams["video"]["pix_fmt"] == "yuv420p"
        assert streams["audio"]["codec_name"] == "aac"
        data = out.read_bytes()
        assert data.find(b"moov") < data.find(b"mdat")

    def test_summary_and_validity(self, job: PipelineContext) -> None:
        summary = read_model(job.paths.summary_json, Summary)
        assert summary.teams == ["IND", "AUS"] and summary.deliveries_found == 2
        assert is_valid_render(job)


class TestTitle:
    def test_team_names(self, job: PipelineContext) -> None:
        text = ocr_text(cv2.imread(str(job.paths.title_png))).upper()  # OCR may read "VS"
        assert "IND VS AUS" in text and "152/3" in text and "5-MINUTE" in text

    def test_default_heading(self, tmp_path: Path) -> None:
        png = make_title(tmp_path / "t.png", [], [], "all", (1280, 720))
        text = ocr_text(cv2.imread(str(png))).upper()
        assert "MATCH HIGHLIGHTS" in text and "EVERY WICKET AND BOUNDARY" in text


class TestAtomicRerender:
    def test_failed_rerender_keeps_old_reel(self, job: PipelineContext, monkeypatch) -> None:
        out = job.paths.reel_path("5min")
        before = out.read_bytes()
        real_run = subprocess.run

        def failing_concat(cmd, *args, **kwargs):
            if "concat" in cmd:
                partial = Path(cmd[-1])
                partial.write_bytes(b"half a file")
                return subprocess.CompletedProcess(cmd, 1, "", "simulated failure")
            return real_run(cmd, *args, **kwargs)

        monkeypatch.setattr(reel_module.subprocess, "run", failing_concat)
        with pytest.raises(RuntimeError, match="Joining the reel failed"):
            render_reel(job, "5min")
        assert out.read_bytes() == before
        assert not re.search(r"\.tmp|parts\.txt", " ".join(p.name for p in out.parent.iterdir()))


class TestEmptyPlan:
    def test_no_highlights_gives_title_only_reel(self, synthetic_match, tmp_path: Path) -> None:
        paths = JobPaths("empty", data_dir=tmp_path)
        paths.ensure_job_dir()
        ctx = PipelineContext(
            job_id="empty",
            db_path=tmp_path / "db",
            paths=paths,
            config=load_config(),
            input_path=synthetic_match.video,
        )
        run_ingest(ctx)
        write_model(paths.scorebox_json, Scorebox(found=False))
        write_model(paths.reel_plan_path("5min"), ReelPlan(mode="5min", duration_s=3.0, clips=[]))
        run_render(ctx)
        duration = float(probe(paths.reel_path("5min"))["format"]["duration"])
        assert abs(duration - 3.0) <= 0.5 and is_valid_render(ctx)
