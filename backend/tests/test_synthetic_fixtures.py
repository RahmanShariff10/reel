"""Tests for slice-03-synthetic-fixtures.

Acceptance criteria:
- Default options produce video.mp4 and schedule.json in under 30 s.
- ffprobe: duration within 0.1 s, 1280x720, audio stream present (none with --no-audio).
- schedule.json lists cuts and scene types, score-box text changes with times, hidden-box
  intervals, the true score-box rectangle, and burst times.
- Same arguments and seed produce an identical schedule.json.
- A frame at a scheduled time, cropped to the true score box, is read correctly by RapidOCR.
- --order wickets-runs shows wickets/runs.
- --distractor shows a static numeric graphic in a different corner for the whole video.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

import cv2
import numpy as np
import pytest
from rapidocr_onnxruntime import RapidOCR

from reel.ingest.probe import find_binary
from tests.conftest import SyntheticMatch, make_synthetic_match
from tests.fixtures.make_synthetic import main, score_text_at


def _probe(video: Path) -> dict:
    out = subprocess.run(
        [find_binary("ffprobe"), "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height", "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _frame(video: Path, t: float) -> np.ndarray:
    out = subprocess.run(
        [find_binary("ffmpeg"), "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
         "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
        capture_output=True, check=True,
    )
    return cv2.imdecode(np.frombuffer(out.stdout, np.uint8), cv2.IMREAD_COLOR)


def _crop(img: np.ndarray, rect: list[int]) -> np.ndarray:
    x, y, w, h = rect
    return img[y:y + h, x:x + w]


def _ocr(img: np.ndarray) -> str:
    result, _ = _OCR(img)
    return " ".join(r[1] for r in result) if result else ""


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


_OCR = RapidOCR()


@pytest.fixture(scope="module")
def short_variants(tmp_path_factory: pytest.TempPathFactory) -> dict[str, SyntheticMatch]:
    base = tmp_path_factory.mktemp("variants")
    return {
        "wickets_runs": make_synthetic_match(base / "wr", duration_s=30.0, order="wickets-runs"),
        "distractor": make_synthetic_match(base / "dis", duration_s=30.0, distractor=True),
        "no_audio": make_synthetic_match(base / "na", duration_s=10.0, has_audio=False),
        "no_scorebox": make_synthetic_match(base / "nsb", duration_s=10.0, scorebox=False),
    }


class TestGeneration:
    def test_default_generation_under_30s(self, tmp_path: Path) -> None:
        start = time.monotonic()
        assert main(["--out", str(tmp_path)]) == 0
        assert time.monotonic() - start < 30.0
        assert (tmp_path / "video.mp4").is_file()
        assert (tmp_path / "schedule.json").is_file()

    def test_probe_matches_request(self, synthetic_match: SyntheticMatch) -> None:
        info = _probe(synthetic_match.video)
        assert abs(float(info["format"]["duration"]) - 120.0) <= 0.1
        video = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (video["width"], video["height"]) == (1280, 720)
        assert any(s["codec_type"] == "audio" for s in info["streams"])

    def test_no_audio_has_no_audio_stream(self, short_variants) -> None:
        info = _probe(short_variants["no_audio"].video)
        assert not any(s["codec_type"] == "audio" for s in info["streams"])
        assert short_variants["no_audio"].schedule["bursts"] == []


class TestSchedule:
    def test_schedule_contents(self, synthetic_match: SyntheticMatch) -> None:
        s = synthetic_match.schedule
        assert s["scorebox_rect"] and len(s["scorebox_rect"]) == 4
        assert len(s["cuts"]) == len(s["shots"]) - 1
        assert set(s["scenes"]) >= {"run_up", "field", "close_up", "crowd", "graphic"}
        assert s["hidden_intervals"] and s["bursts"]
        events = {c["event"] for c in s["score_changes"]}
        assert {"four", "six", "wicket", "wicket_overturned", "innings_start"} <= events
        times = [c["time_s"] for c in s["score_changes"]]
        assert times == sorted(times)

    def test_shots_cover_video_without_gaps(self, synthetic_match: SyntheticMatch) -> None:
        shots = synthetic_match.schedule["shots"]
        assert shots[0]["start_s"] == 0.0
        assert shots[-1]["end_s"] == synthetic_match.schedule["duration_s"]
        for a, b in zip(shots, shots[1:]):
            assert a["end_s"] == b["start_s"]

    def test_score_changes_never_in_hidden_intervals(self, synthetic_match) -> None:
        s = synthetic_match.schedule
        for ch in s["score_changes"]:
            assert not any(h0 <= ch["time_s"] < h1 for h0, h1 in s["hidden_intervals"])

    def test_same_seed_same_schedule(self, tmp_path: Path) -> None:
        a = make_synthetic_match(tmp_path / "a", duration_s=15.0, seed=7)
        b = make_synthetic_match(tmp_path / "b", duration_s=15.0, seed=7)
        assert a.schedule_path.read_text() == b.schedule_path.read_text()


class TestRendering:
    def test_score_box_readable_by_ocr(self, synthetic_match: SyntheticMatch) -> None:
        s = synthetic_match.schedule
        checked = 0
        for ch in s["score_changes"][1:6]:
            t = ch["time_s"] + 1.0
            expected = score_text_at(s, t)
            if expected is None:
                continue
            text = _ocr(_crop(_frame(synthetic_match.video, t), s["scorebox_rect"]))
            assert _norm(text) == _norm(expected), (t, text, expected)
            checked += 1
        assert checked >= 3

    def test_score_box_hidden_during_replays(self, synthetic_match: SyntheticMatch) -> None:
        s = synthetic_match.schedule
        h0, h1 = s["hidden_intervals"][0]
        text = _ocr(_crop(_frame(synthetic_match.video, (h0 + h1) / 2), s["scorebox_rect"]))
        assert not re.search(r"\d+/\d+", text)

    def test_wickets_runs_order(self, short_variants) -> None:
        m = short_variants["wickets_runs"]
        ch = m.schedule["score_changes"][0]
        assert ch["text"].split()[1] == f"{ch['wickets']}/{ch['runs']}"
        text = _ocr(_crop(_frame(m.video, 1.0), m.schedule["scorebox_rect"]))
        assert f"{ch['wickets']}/{ch['runs']}" in _norm(text)

    def test_distractor_static_in_other_corner(self, short_variants) -> None:
        m = short_variants["distractor"]
        s = m.schedule
        dx, dy, _, _ = s["distractor_rect"]
        bx, by, _, _ = s["scorebox_rect"]
        assert abs(dx - bx) > s["width"] / 2 and abs(dy - by) > s["height"] / 2
        for t in (0.5, 15.0, 29.0):
            text = _ocr(_crop(_frame(m.video, t), s["distractor_rect"]))
            assert _norm(text) == _norm(s["distractor_text"])

    def test_no_scorebox_variant(self, short_variants) -> None:
        s = short_variants["no_scorebox"].schedule
        assert s["scorebox_rect"] is None and s["score_changes"] == []
