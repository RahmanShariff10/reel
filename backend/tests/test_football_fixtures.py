"""Tests for slice-37-football-fixtures.

Acceptance criteria:
- A generated video matches the requested duration, resolution and audio.
- The schedule lists goals, score-update times, replays, half boundaries, bursts and shots.
- The same seed gives an identical schedule.
- For each graphic style, a sampled frame's OCR contains the scheduled score and clock.
- At least one goal, overturned goal, replay, half-time break and no-goal burst are included.
- A 3-minute video is generated in under 60 s.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from rapidocr_onnxruntime import RapidOCR

from reel.ingest.probe import find_binary
from tests.fixtures.make_football import (
    build_schedule,
    clock_text_at,
    generate_football_video,
    main,
    score_text_at,
)

_OCR = RapidOCR()


def _probe(video: Path) -> dict[str, Any]:
    out = subprocess.run(
        [
            find_binary("ffprobe"),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(video),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def _frame(video: Path, t: float) -> np.ndarray:
    out = subprocess.run(
        [
            find_binary("ffmpeg"),
            "-v",
            "error",
            "-ss",
            f"{t:.2f}",
            "-i",
            str(video),
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


def _ocr_box(video: Path, schedule: dict[str, Any], t: float) -> str:
    x, y, w, h = schedule["scorebox_rect"]
    result, _ = _OCR(_frame(video, t)[y : y + h, x : x + w])
    return " ".join(r[1] for r in result) if result else ""


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _visible_time_after(schedule: dict[str, Any], t: float) -> float:
    """A mid-second time just after ``t`` when the graphic is on screen."""
    candidate = float(int(t) + 1) + 0.5
    while score_text_at(schedule, candidate) is None:
        candidate += 1.0
    return candidate


@pytest.fixture(scope="module")
def default_match(tmp_path_factory: pytest.TempPathFactory):
    out = tmp_path_factory.mktemp("football")
    start = time.monotonic()
    video, schedule_path = generate_football_video(out)
    return video, json.loads(schedule_path.read_text()), time.monotonic() - start


class TestGeneration:
    def test_three_minute_video_under_60s(self, default_match) -> None:
        _, _, elapsed = default_match
        assert elapsed < 60.0

    def test_probe_matches_request(self, default_match) -> None:
        video, _, _ = default_match
        info = _probe(video)
        assert abs(float(info["format"]["duration"]) - 180.0) <= 0.1
        stream = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (stream["width"], stream["height"]) == (1280, 720)
        assert any(s["codec_type"] == "audio" for s in info["streams"])

    def test_no_audio_and_custom_size(self, tmp_path: Path) -> None:
        assert (
            main(["--out", str(tmp_path), "--duration", "150", "--no-audio", "--seed", "3"]) == 0
        )
        info = _probe(tmp_path / "video.mp4")
        assert abs(float(info["format"]["duration"]) - 150.0) <= 0.1
        assert not any(s["codec_type"] == "audio" for s in info["streams"])
        assert json.loads((tmp_path / "schedule.json").read_text())["bursts"] == []


class TestSchedule:
    def test_lists_everything(self) -> None:
        s = build_schedule()
        for key in (
            "goals",
            "score_changes",
            "replays",
            "halves",
            "bursts",
            "shots",
            "cuts",
            "scorebox_rect",
            "clock_rect",
        ):
            assert s[key], key
        for goal in s["goals"]:
            assert goal["t_update_s"] > goal["t_goal_s"]

    def test_required_events_present(self) -> None:
        s = build_schedule()
        assert any(not g["overturned"] for g in s["goals"])
        assert any(g["overturned"] for g in s["goals"])
        assert s["replays"]
        assert s["halves"][1]["start_s"] > s["halves"][0]["end_s"]
        assert s["halves"][0]["clock_start_s"] != s["halves"][1]["clock_start_s"]
        assert any(b["kind"] == "chance" for b in s["bursts"])
        goal_times = [g["t_goal_s"] for g in s["goals"]]
        for burst in (b for b in s["bursts"] if b["kind"] == "chance"):
            assert all(abs(burst["start_s"] - t) > 10 for t in goal_times)

    def test_same_seed_same_schedule(self, tmp_path: Path) -> None:
        assert build_schedule(seed=7) == build_schedule(seed=7)
        assert build_schedule(seed=7)["shots"] != build_schedule(seed=8)["shots"]

    def test_shots_cover_video_without_gaps(self) -> None:
        s = build_schedule()
        assert s["shots"][0]["start_s"] == 0.0
        assert s["shots"][-1]["end_s"] == s["duration_s"]
        for a, b in zip(s["shots"], s["shots"][1:]):
            assert a["end_s"] == b["start_s"]
            assert b["end_s"] > b["start_s"]

    @pytest.mark.parametrize("duration", [150.0, 180.0, 600.0])
    def test_every_cut_is_visible(self, duration: float) -> None:
        # Scenes are flat colours, so a cut between two shots of one scene can't be seen.
        s = build_schedule(duration_s=duration)
        for a, b in zip(s["shots"], s["shots"][1:]):
            assert a["scene"] != b["scene"], (a, b)

    def test_scenes_are_football_shot_labels(self) -> None:
        assert set(build_schedule()["scenes"]) == {"wide", "medium", "close_up", "crowd", "graphic"}

    def test_score_changes_are_visible(self) -> None:
        s = build_schedule()
        for change in s["score_changes"][1:]:
            assert not any(h0 <= change["time_s"] < h1 for h0, h1 in s["hidden_intervals"])

    def test_final_score_reflects_overturned_goal(self) -> None:
        s = build_schedule()
        assert (s["score_changes"][-1]["home"], s["score_changes"][-1]["away"]) == (2, 1)
        assert s["final_score"] == "ARS 2-1 CHE"

    def test_clock_restart_is_configurable(self) -> None:
        s = build_schedule(second_half_clock_s=0)
        start = s["halves"][1]["start_s"]
        assert clock_text_at(s, start + 5.5) == "00:05"

    def test_rejects_bad_arguments(self) -> None:
        with pytest.raises(ValueError):
            build_schedule(style="fancy")
        with pytest.raises(ValueError):
            build_schedule(duration_s=30.0)

    def test_no_graphic_and_static_caption_options(self) -> None:
        none = build_schedule(scorebox=False)
        assert none["scorebox_rect"] is None and none["clock_rect"] is None
        assert all(score_text_at(none, t) is None for t in range(0, 180, 5))
        assert build_schedule()["distractor_rect"] is None
        caption = build_schedule(distractor=True)["distractor_rect"]
        assert caption and caption[0] > 640 and caption[1] > 360  # bottom right


class TestRendering:
    @pytest.mark.parametrize(
        ("style", "marker"), [("dash", "1-0"), ("space", "10"), ("colon", "1:0")]
    )
    def test_ocr_reads_score_and_clock(
        self, tmp_path: Path, style: str, marker: str, default_match
    ) -> None:
        if style == "dash":
            video, schedule, _ = default_match
        else:
            video, path = generate_football_video(tmp_path, style=style)
            schedule = json.loads(path.read_text())
        goal = schedule["goals"][0]
        t = _visible_time_after(schedule, goal["t_update_s"] + 8.0)

        text = _norm(_ocr_box(video, schedule, t))

        assert _norm(score_text_at(schedule, t)) in text, (t, text)
        assert marker in text
        assert clock_text_at(schedule, t) in text, (t, text)

    def test_clock_ticks(self, default_match) -> None:
        video, schedule, _ = default_match
        t = schedule["halves"][0]["start_s"] + 3.5
        first = clock_text_at(schedule, t)
        second = clock_text_at(schedule, t + 7.0)
        assert first != second
        assert first in _norm(_ocr_box(video, schedule, t))
        assert second in _norm(_ocr_box(video, schedule, t + 7.0))

    def test_graphic_hidden_during_replay_and_half_time(self, default_match) -> None:
        video, schedule, _ = default_match
        r0, r1 = schedule["replays"][0]
        half_time = (schedule["halves"][0]["end_s"] + schedule["halves"][1]["start_s"]) / 2
        for t in ((r0 + r1) / 2, half_time):
            assert not re.search(r"\d\d:\d\d", _ocr_box(video, schedule, t)), t

    def test_second_half_clock_restarts(self, default_match) -> None:
        video, schedule, _ = default_match
        t = schedule["halves"][1]["start_s"] + 3.5
        assert clock_text_at(schedule, t) == "45:03"
        assert "45:03" in _norm(_ocr_box(video, schedule, t))

    def test_overturned_goal_disappears(self, default_match) -> None:
        video, schedule, _ = default_match
        goal = next(g for g in schedule["goals"] if g["overturned"])
        during = _visible_time_after(schedule, goal["t_update_s"] + 2.0)
        after = _visible_time_after(schedule, goal["t_overturn_s"] + 1.0)
        assert "2-1" in _norm(_ocr_box(video, schedule, during))
        assert "1-1" in _norm(_ocr_box(video, schedule, after))

    def test_static_caption_and_no_graphic(self, football_variants) -> None:
        video, schedule = (football_variants["colon_caption"].video,
                           football_variants["colon_caption"].schedule)
        x, y, w, h = schedule["distractor_rect"]
        for t in (20.5, 120.5):
            result, _ = _OCR(_frame(video, t)[y : y + h, x : x + w])
            assert result and _norm(result[0][1]) == "12:30", t

        bare = football_variants["no_graphic"].video
        result, _ = _OCR(_frame(bare, 60.5))
        assert not any(re.search(r"\d\d:\d\d", r[1]) for r in result or [])
