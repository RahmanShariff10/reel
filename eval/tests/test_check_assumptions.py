"""Tests for slice-38-real-match-check, using only synthetic video and stubs.

Acceptance criteria:
- Given synthetic inputs with known answers, A1, A2 and A3 report them correctly.
- Given a run, the report contains no images or broadcast text beyond team codes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from reel.common.config import load_config
from reel.ingest.frames import grab_frame
from reel.ingest.probe import find_binary, probe_video
from reel.scoreboard.ocr import OcrItem, read_text

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from tests.fixtures.make_football import (  # noqa: E402
    build_schedule,
    clock_seconds_at,
    generate_football_video,
)

from eval.check_assumptions import (  # noqa: E402
    AudioCheck,
    ClockCheck,
    MatchResult,
    ReplayCheck,
    WhisperLanguageDetector,
    check_match,
    detect_language,
    load_games,
    measure_audio,
    measure_clock,
    measure_replays,
    parse_clock,
    recommend,
    report_markdown,
    shot_midpoints,
)
from eval.soccernet import CameraLabel, Label  # noqa: E402

CFG = load_config()
BOX = (50, 30, 200, 40)
FRAME = np.zeros((720, 1280, 3), np.uint8)


def item(text: str, rect=BOX) -> OcrItem:
    return OcrItem(rect=rect, text=text, confidence=0.9)


def goal(half: int, seconds: float, label: str = "Goal") -> Label:
    return Label(half=half, game_time="", position_ms=int(seconds * 1000), label=label)


class TestParseClock:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("34:12", 2052),
            ("ARS 1-0 CHE 34:12", 2052),
            ("5:03", 303),
            ("105:30", 6330),
            ("MCI 2:1 LIV", None),
            ("12:75", None),
            ("no clock here", None),
        ],
    )
    def test_parse(self, text: str, expected: int | None) -> None:
        assert parse_clock(text) == expected


class TestClockLogic:
    def _points(self) -> list[tuple[int, float]]:
        return [(1, t * 75.0) for t in range(1, 21)]

    def _run(self, text_at) -> ClockCheck:
        current = {}

        def read_frame(half: int, t: float):
            current["t"] = t
            return FRAME

        return measure_clock(
            self._points(), read_frame, lambda _: text_at(current["t"]), CFG.scoreboard
        )

    def test_running_clock_is_found(self) -> None:
        check = self._run(lambda t: [item(f"{int(t) // 60:02d}:{int(t) % 60:02d}")])
        assert check.found and check.presence == 1.0 and check.linearity == 1.0
        assert check.box == BOX

    def test_static_time_is_rejected(self) -> None:
        check = self._run(lambda t: [item("12:30")])
        assert not check.found and check.linearity == 0.0

    def test_running_clock_beats_static_text(self) -> None:
        other = (900, 600, 100, 30)
        check = self._run(
            lambda t: [item("12:30", other), item(f"{int(t) // 60:02d}:{int(t) % 60:02d}")]
        )
        assert check.found and check.box == BOX

    def test_rarely_visible_clock_is_rejected(self) -> None:
        check = self._run(
            lambda t: [item(f"{int(t) // 60:02d}:{int(t) % 60:02d}")] if t <= 300 else []
        )
        assert not check.found and check.presence == pytest.approx(0.2)

    def test_no_frames(self) -> None:
        check = measure_clock([(1, 1.0)], lambda h, t: None, lambda _: [], CFG.scoreboard)
        assert not check.found


class TestReplayLogic:
    def test_shot_midpoints(self) -> None:
        cams = [
            CameraLabel(half=1, game_time="", position_ms=0, label="a", replay=False),
            CameraLabel(half=1, game_time="", position_ms=10_000, label="b", replay=True),
        ]
        assert shot_midpoints(cams, {1: 30.0}) == [(1, 5.0, False), (1, 20.0, True)]

    def test_known_hidden_rates(self) -> None:
        shots = [(1, float(i), i % 2 == 0) for i in range(20)]

        def read_frame(half: int, t: float):
            frame = FRAME.copy()
            frame[0, 0, 0] = 1 if int(t) % 2 == 0 else 0
            return frame

        def ocr(crop: np.ndarray) -> list[OcrItem]:
            return [] if crop[0, 0, 0] == 1 else [item("10:00")]

        check = measure_replays(shots, read_frame, (0, 0, 20, 20), ocr)
        assert check.replay_hidden == 1.0 and check.live_hidden == 0.0
        assert (check.replay_shots, check.live_shots) == (10, 10)


class TestAudioLogic:
    def _series(self, peaks: list[int], n: int = 600) -> list[float]:
        values = np.zeros(n)
        for p in peaks:
            values[max(0, p - 1) : p + 2] = 0.9
        return values.tolist()

    def test_known_answers(self) -> None:
        labels = [
            goal(1, 0.0, "Kick-off"),
            goal(1, 100.0),
            goal(1, 300.0),
            goal(1, 200.0, "Shots on target"),
            goal(1, 400.0, "Shots on target"),
            goal(1, 600.0, "Throw-in"),
        ]
        check = measure_audio({1: self._series([105, 410])}, labels, CFG.moments)
        assert (check.goals, check.goals_near_peak) == (2, 1)
        assert (check.shots, check.shots_near_peak) == (2, 1)
        assert check.goal_recall == 0.5 and check.shot_recall == 0.5
        assert check.peaks_per_min == pytest.approx(0.2, abs=0.01)
        assert check.chance_level == pytest.approx(62 / 600, abs=0.01)

    def test_labels_in_other_half_do_not_match(self) -> None:
        check = measure_audio(
            {1: self._series([105]), 2: self._series([300])}, [goal(2, 105.0)], CFG.moments
        )
        assert check.goals == 1 and check.goals_near_peak == 0

    def test_no_peaks(self) -> None:
        check = measure_audio({1: [0.1] * 300}, [goal(1, 100.0)], CFG.moments)
        assert check.goals_near_peak == 0


class TestRecommend:
    def _result(self, found=True, replay=0.95, live=0.05, near=9, chance=0.3) -> MatchResult:
        return MatchResult(
            game="g",
            clock=ClockCheck(found=found, presence=0.9, linearity=0.9),
            replays=ReplayCheck(replay, live, 10, 10),
            audio=AudioCheck(goals=10, goals_near_peak=near, chance_level=chance),
        )

    def test_all_hold(self) -> None:
        text = recommend([self._result()])
        assert all(v.startswith("Holds") for v in text.values())

    def test_failures_say_what_to_change(self) -> None:
        text = recommend([self._result(found=False, replay=0.3, near=4)])
        assert text["A1 clock"].startswith("Check needed")
        assert "slice 44" in text["A2 replays"]
        assert "slice 43" in text["A3 audio"]

    def test_peak_rate_at_chance_does_not_count(self) -> None:
        assert "Does not hold" in recommend([self._result(near=9, chance=0.85)])["A3 audio"]

    def test_replay_not_measured(self) -> None:
        text = recommend([self._result(replay=None, live=None)])
        assert text["A2 replays"].startswith("Not measured")


class StubDetector:
    def __init__(self, language: str) -> None:
        self.language = language
        self.calls = 0

    def detect(self, wav: Path) -> str:
        self.calls += 1
        assert wav.is_file()
        return self.language


def _cut(video: Path, start: float, end: float, out: Path) -> None:
    subprocess.run(
        [
            find_binary("ffmpeg"),
            "-y",
            "-v",
            "error",
            "-ss",
            f"{start:.2f}",
            "-i",
            str(video),
            "-t",
            f"{end - start:.2f}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            str(out),
        ],
        check=True,
    )


@pytest.fixture(scope="module")
def synthetic_game(tmp_path_factory: pytest.TempPathFactory):
    """A synthetic match laid out like SoccerNet: one file per half, plus label files."""
    root = tmp_path_factory.mktemp("assumptions")
    video, path = generate_football_video(root / "source", style="space")
    schedule = json.loads(path.read_text())

    game = "league/season/Team A 2 - 1 Team B"
    videos, labels = root / "videos", root / "labels"
    (videos / game).mkdir(parents=True)
    (labels / game).mkdir(parents=True)
    halves = schedule["halves"]
    for half in halves:
        _cut(
            video,
            half["start_s"],
            half["end_s"],
            videos / game / f"{half['half']}_720p.mkv",
        )

    def relative_ms(t: float, half: dict) -> str:
        return str(round((t - half["start_s"]) * 1000))

    annotations = [
        {
            "gameTime": f"{g['half']} - 00:00",
            "label": "Goal",
            "position": relative_ms(g["t_goal_s"], halves[g["half"] - 1]),
            "team": g["side"],
            "visibility": "visible",
        }
        for g in schedule["goals"]
    ]
    for half in halves:
        annotations.append(
            {"gameTime": f"{half['half']} - 00:00", "label": "Kick-off", "position": "0"}
        )
    (labels / game / "Labels-v2.json").write_text(json.dumps({"annotations": annotations}))

    cameras = []
    for shot in schedule["shots"]:
        half = next(
            (h for h in halves if h["start_s"] <= shot["start_s"] < h["end_s"]), None
        )
        if half is None:
            continue
        cameras.append(
            {
                "gameTime": f"{half['half']} - 00:00",
                "label": shot["scene"],
                "position": relative_ms(shot["start_s"], half),
                "replay": "replay" if shot["replay"] else "real-time",
            }
        )
    (labels / game / "Labels-cameras.json").write_text(json.dumps({"annotations": cameras}))
    return game, videos, labels, schedule, video


class TestSyntheticMatch:
    """Known answers from the synthetic broadcast, with real OCR on real frames."""

    def test_clock_is_located(self, synthetic_game) -> None:
        *_, schedule, video = synthetic_game
        meta = probe_video(video)
        half = schedule["halves"][0]
        points = [(1, half["start_s"] + 4.5 + i * 3.0) for i in range(8)]
        replays = schedule["replays"]
        points = [
            p for p in points if not any(a - 1 <= p[1] <= b + 1 for a, b in replays)
        ]

        def read_frame(_: int, t: float):
            return grab_frame(video, t, meta.width, meta.height)

        check = measure_clock(points, read_frame, read_text, CFG.scoreboard)

        assert check.found and check.presence == 1.0
        x, y, w, h = schedule["scorebox_rect"]
        bx, by, bw, bh = check.box
        assert x <= bx and bx + bw <= x + w + 5
        assert y - 5 <= by and by + bh <= y + h + 5

    def test_schedule_clock_helper_is_consistent(self) -> None:
        s = build_schedule()
        assert clock_seconds_at(s, s["halves"][0]["start_s"] + 3.5) == 1803

    def test_whole_match_and_report(self, synthetic_game, tmp_path: Path) -> None:
        game, videos, labels, schedule, _ = synthetic_game
        detector = StubDetector("en")

        result = check_match(
            game,
            videos,
            labels,
            CFG,
            read_text,
            tagger=None,
            detector=detector,
            sample_frames=20,
            max_shots_per_class=6,
        )

        assert result.clock.found
        assert result.replays.replay_shots == len(schedule["replays"])
        assert result.replays.replay_hidden == 1.0
        assert result.replays.live_hidden == 0.0
        assert result.audio.goals == len(schedule["goals"])
        assert result.audio.goals_near_peak == len(schedule["goals"])
        assert result.language == "en" and detector.calls == 5

        text = report_markdown([result])
        assert "Team A 2 - 1 Team B" in text
        assert "Holds: box hidden in 100% of replay shots" in text
        for forbidden in ("![", "<img", ".jpg", ".png", "ARS", "CHE"):
            assert forbidden not in text

    def test_missing_labels_named(self, synthetic_game, tmp_path: Path) -> None:
        game, videos, *_ = synthetic_game
        with pytest.raises(FileNotFoundError, match="Labels-v2.json"):
            check_match(game, videos, tmp_path, CFG, read_text, None, None, sample_frames=2)


class TestManifest:
    def test_only_game_required(self, tmp_path: Path) -> None:
        path = tmp_path / "m.yaml"
        path.write_text("matches:\n  - game: a/b/c\n  - d/e/f\n")
        assert load_games(path) == ["a/b/c", "d/e/f"]

    def test_missing_game_named(self, tmp_path: Path) -> None:
        path = tmp_path / "m.yaml"
        path.write_text("matches:\n  - split: dev\n")
        with pytest.raises(ValueError, match="#0"):
            load_games(path)


def test_language_majority(tmp_path: Path, synthetic_game) -> None:
    *_, video = synthetic_game

    class Votes:
        answers = iter(["fr", "en", "en"])

        def detect(self, wav: Path) -> str:
            return next(self.answers)

    assert detect_language([(video, 170.0)], Votes(), windows=3) == "en"


def test_whisper_detector_passes_samples_not_a_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """faster-whisper's own file decoding crashes on PyAV 19, so it must be given samples."""
    received = []

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def transcribe(self, audio, beam_size):
            received.append(audio)
            return [], type("Info", (), {"language": "en"})()

    monkeypatch.setattr("faster_whisper.WhisperModel", FakeModel)
    wav = tmp_path / "window.wav"
    sf.write(wav, np.zeros(16000, dtype=np.float32), 16000)

    assert WhisperLanguageDetector("small", "int8", tmp_path).detect(wav) == "en"

    assert isinstance(received[0], np.ndarray)
    assert received[0].dtype == np.float32
    assert received[0].shape == (16000,)
