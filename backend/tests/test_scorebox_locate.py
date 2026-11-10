"""Tests for slice-39-clock-scorebox-locate.

Acceptance criteria:
- Synthetic videos in each graphic style: the box is found within 10 px of the true position.
- A static ``12:30`` caption elsewhere on screen is not selected.
- A video with no graphic: ``found: false`` and the stage succeeds.
- OCR that merges clock and score into one item: ``clock_box`` still covers the clock digits.
- ``MCI 2:1 LIV 67:05``: ``2:1`` is not taken for a clock and ``67:05`` is.
- ``45:00+2`` parses as a clock of 45:00 plus 2 added minutes.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from reel.common.config import ReelConfig, ScoreboardConfig, load_config
from reel.common.models import Scorebox, read_model
from reel.common.paths import JobPaths
from reel.ingest.probe import probe_video
from reel.ingest.stage import is_valid_ingest, run_ingest
from reel.jobs.pipeline import PipelineContext, Stage, run_pipeline
from reel.jobs.store import claim_next_job, create_job, get_job, init_db
from reel.scoreboard.locate import (
    clock_advances,
    frame_reader,
    linearity,
    locate_scorebox,
    sample_times,
    score_line,
)
from reel.scoreboard.ocr import OcrItem, read_text
from reel.scoreboard.parse import find_clock, find_goals
from reel.scoreboard.stage import is_valid_locate_scorebox, run_locate_scorebox
from tests.conftest import SyntheticMatch
from tests.fixtures.make_football import clock_seconds_at, score_text_at

FAST = {"scoreboard": {"sample_frames": 30}}  # fewer OCR calls; still clears every threshold


def run_locate(
    video: Path, tmp: Path, config: ReelConfig | None = None
) -> tuple[Scorebox, JobPaths]:
    paths = JobPaths("job", data_dir=tmp)
    paths.ensure_job_dir()
    ctx = PipelineContext(job_id="job", db_path=tmp / "reel.db", paths=paths,
                          config=config or load_config(overrides=FAST), input_path=video)
    run_ingest(ctx)
    run_locate_scorebox(ctx)
    return read_model(paths.scorebox_json, Scorebox), paths


def edges(rect: list[int] | tuple[int, ...]) -> tuple[int, int, int, int]:
    x, y, w, h = rect
    return x, y, x + w, y + h


def within_px(rect: list[int], truth: list[int], px: int = 10) -> bool:
    return all(abs(a - b) <= px for a, b in zip(edges(rect), edges(truth)))


def overlaps(a: list[int] | tuple[int, ...], b: list[int] | tuple[int, ...]) -> bool:
    ax0, ay0, ax1, ay1 = edges(a)
    bx0, by0, bx1, by1 = edges(b)
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def item(text: str, x: int, y: int = 50, w: int = 60, h: int = 30) -> OcrItem:
    return OcrItem((x, y, w, h), text, 0.9)


@pytest.fixture(scope="module")
def videos(football_variants: dict[str, SyntheticMatch]) -> dict[str, SyntheticMatch]:
    return football_variants


class TestClockParse:
    def test_clock_beside_a_colon_score(self) -> None:
        text = "MCI 2:1 LIV 67:05"
        clock = find_clock(text)
        assert clock is not None and clock.seconds == 67 * 60 + 5
        assert text[clock.start : clock.end] == "67:05"
        assert find_goals(text) == (2, 1)

    @pytest.mark.parametrize("text", ["45:00+2", "45:00 + 2", "45:00+2'"])
    def test_added_minutes(self, text: str) -> None:
        clock = find_clock(text)
        assert clock is not None and clock.seconds == 45 * 60 and clock.added_min == 2

    @pytest.mark.parametrize(
        ("text", "seconds"), [("67:05", 4025), ("9:59", 599), ("102:30", 6150), ("ARS 34:14", 2054)]
    )
    def test_clock_values(self, text: str, seconds: int) -> None:
        clock = find_clock(text)
        assert clock is not None and clock.seconds == seconds and clock.added_min is None

    @pytest.mark.parametrize("text", ["2:1", "ARS 1-0 CHE", "45:60", "12:345", "8.25", ""])
    def test_not_clocks(self, text: str) -> None:
        assert find_clock(text) is None


class TestGoalsParse:
    @pytest.mark.parametrize(
        ("text", "goals"),
        [
            ("ARS 1-0 CHE", (1, 0)),
            ("ARS 1 0 CHE", (1, 0)),
            ("ARS 1:0 CHE", (1, 0)),
            ("RMA 0 | 0 BAR", (0, 0)),
            ("MCI 2:1 LIV 67:05", (2, 1)),
            ("ARSO-O CHE", (0, 0)),  # OCR read 0 as the letter O
            ("ARS10CHE", (1, 0)),  # OCR dropped the spaces
            # Seen on a real broadcast: a 0-0 score read as letters, spaced or glued
            ("OM OO PARIS SG", (0, 0)),
            ("OM OOPARIS SG", (0, 0)),
            ("OM 23PARISSG", (2, 3)),
            ("OM 0 O PARIS SG", (0, 0)),
            ("OM 0 OPARIS SG", (0, 0)),
            ("OM O PARIS SG", None),  # one zero dropped: unreadable, not 0-0
            ("GOOD TOO", None),
            ("ROONEY 1-0", (1, 0)),
            ("ARS 12-3 CHE", (12, 3)),
            ("67:05", None),
            ("ARS 16-0 CHE", None),
            ("no score", None),
        ],
    )
    def test_goals(self, text: str, goals: tuple[int, int] | None) -> None:
        assert find_goals(text) == goals


class TestLinearity:
    cfg = ScoreboardConfig()

    @pytest.mark.parametrize(
        ("dt", "dclock", "ok"),
        [
            (80.0, 80, True),
            (80.0, 50, False),  # too slow
            (10.0, 20, False),  # too fast
            (1.7, 1, True),  # whole-second clock read 1.7 s apart
            (1.7, 2, True),
            (1.7, 0, False),  # static text never passes
            (80.0, -2000, False),  # half-time restart
        ],
    )
    def test_clock_advances(self, dt: float, dclock: int, ok: bool) -> None:
        assert clock_advances(dt, dclock, self.cfg) is ok

    def test_share_of_pairs(self) -> None:
        def hits(pairs: list[tuple[float, int]]) -> list[SimpleNamespace]:
            return [SimpleNamespace(time_s=t, clock=SimpleNamespace(seconds=c)) for t, c in pairs]

        ticking = hits([(0, 100), (10, 110), (20, 120), (30, 130)])
        static = hits([(0, 750), (10, 750), (20, 750)])
        assert linearity(ticking, self.cfg) == 1.0
        assert linearity(static, self.cfg) == 0.0
        assert linearity(ticking[:1], self.cfg) == 0.0


class TestScoreLine:
    cfg = ScoreboardConfig()

    def test_separate_items(self) -> None:
        items = [item("ARS", 10), item("1-0", 75), item("CHE", 140), item("34:14", 260)]
        line = score_line(items[3], items, self.cfg)
        assert line is not None and not line.merged
        assert line.text == "ARS 1-0 CHE 34:14"
        assert line.rect == (10, 50, 310, 30)

    def test_merged_item(self) -> None:
        merged = item("ARS 1-0 CHE 34:14", 10, w=300)
        line = score_line(merged, [merged], self.cfg)
        assert line is not None and line.merged

    def test_score_on_the_line_above(self) -> None:
        clock, score = item("34:14", 40, y=90), item("ARS 1-0 CHE", 10, y=50, w=120)
        line = score_line(clock, [clock, score], self.cfg)
        assert line is not None and find_goals(line.text) == (1, 0)

    def test_no_score_or_too_far(self) -> None:
        clock = item("34:14", 900)
        assert score_line(clock, [clock, item("SKY", 980)], self.cfg) is None
        assert score_line(clock, [clock, item("ARS 1-0 CHE", 10, w=120)], self.cfg) is None


class TestLocateRules:
    """Decision rules with scripted OCR, so no video is needed."""

    cfg = ScoreboardConfig(sample_frames=20)

    @staticmethod
    def blank(t: float) -> np.ndarray:
        return np.zeros((720, 1280, 3), np.uint8)

    def test_static_caption_loses_to_ticking_clock(self) -> None:
        def ocr(frame_t: float):
            clock = f"{30 + int(frame_t) // 60}:{int(frame_t) % 60:02d}"
            return [item("ARS 1-0 CHE", 60, w=200), item(clock, 380), item("12:30", 1100, y=640)]

        frames: dict[int, float] = {}

        def read_frame(t: float) -> np.ndarray:
            img = self.blank(t)
            frames[id(img)] = t
            return img

        result = locate_scorebox(
            read_frame, 3600.0, 1280, 720, self.cfg, read_ocr=lambda f: ocr(frames[id(f)])
        )
        assert result.found and result.clock_box is not None
        assert overlaps(result.clock_box, (380, 50, 60, 30))
        assert not overlaps(result.box, (1100, 640, 60, 30))

    def test_only_a_static_caption_is_not_found(self) -> None:
        result = locate_scorebox(
            self.blank, 3600.0, 1280, 720, self.cfg,
            read_ocr=lambda f: [item("ARS 1-0 CHE", 60, w=200), item("12:30", 380)],
        )
        assert not result.found and result.box is None

    def test_clock_without_a_score_is_not_found(self) -> None:
        frames: dict[int, float] = {}

        def read_frame(t: float) -> np.ndarray:
            img = self.blank(t)
            frames[id(img)] = t
            return img

        def ocr(frame: np.ndarray) -> list[OcrItem]:
            t = int(frames[id(frame)])
            return [item(f"{t // 60}:{t % 60:02d}", 380)]

        assert not locate_scorebox(read_frame, 3600.0, 1280, 720, self.cfg, read_ocr=ocr).found

    def test_sample_times_long_and_short(self) -> None:
        cfg = ScoreboardConfig(sample_frames=10)
        long = sample_times(3600.0, cfg)
        assert len(long) == 10 and long[0] >= 300 and long[-1] <= 3300
        short = sample_times(100.0, cfg)
        assert short[0] >= 5.0 and short[-1] <= 95.0


def check_found(sb: Scorebox, schedule: dict, paths: JobPaths) -> None:
    assert sb.found and sb.box is not None and sb.clock_box is not None
    assert within_px(sb.box, schedule["scorebox_rect"]), (sb.box, schedule["scorebox_rect"])
    assert overlaps(sb.clock_box, schedule["clock_rect"])
    bx0, by0, bx1, by1 = edges(sb.box)
    cx0, cy0, cx1, cy1 = edges(sb.clock_box)
    assert bx0 <= cx0 and by0 <= cy0 and cx1 <= bx1 and cy1 <= by1
    assert sb.sample_reading and sb.sample_time_s is not None
    truth = score_text_at(schedule, sb.sample_time_s)
    assert find_goals(sb.sample_reading) == find_goals(truth), (sb.sample_reading, truth)
    clock = find_clock(sb.sample_reading)
    assert clock and abs(clock.seconds - clock_seconds_at(schedule, sb.sample_time_s)) <= 1
    assert paths.scorebox_preview_jpg.is_file()


class TestLocateSynthetic:
    def test_dash_style(self, synthetic_match: SyntheticMatch, tmp_path: Path) -> None:
        sb, paths = run_locate(synthetic_match.video, tmp_path)
        check_found(sb, synthetic_match.schedule, paths)

    def test_space_style(self, videos, tmp_path: Path) -> None:
        sb, paths = run_locate(videos["space"].video, tmp_path)
        check_found(sb, videos["space"].schedule, paths)

    def test_colon_style_with_static_caption(self, videos, tmp_path: Path) -> None:
        match = videos["colon_caption"]
        sb, paths = run_locate(match.video, tmp_path)
        check_found(sb, match.schedule, paths)
        assert not overlaps(sb.box, match.schedule["distractor_rect"])

    def test_default_sampling_on_the_shared_match(self, scanned_match: PipelineContext,
                                                  synthetic_match: SyntheticMatch) -> None:
        sb = read_model(scanned_match.paths.scorebox_json, Scorebox)
        check_found(sb, synthetic_match.schedule, scanned_match.paths)

    def test_threshold_from_config(self, synthetic_match: SyntheticMatch, tmp_path: Path) -> None:
        # The graphic is hidden before kick-off, at half-time and during replays.
        strict = load_config(overrides={"scoreboard": {"sample_frames": 30,
                                                       "min_valid_ratio": 0.99}})
        sb, _ = run_locate(synthetic_match.video, tmp_path, strict)
        assert not sb.found


def merge_lines(items: list[OcrItem]) -> list[OcrItem]:
    """Simulate OCR that returns each line of text as one item."""
    lines: list[list[OcrItem]] = []
    for it in sorted(items, key=lambda i: i.rect[0]):
        line = next((ln for ln in lines if abs(ln[0].rect[1] - it.rect[1]) < it.rect[3]), None)
        if line is None:
            lines.append([it])
        else:
            line.append(it)
    merged = []
    for line in lines:
        x0 = min(i.rect[0] for i in line)
        y0 = min(i.rect[1] for i in line)
        x1 = max(i.rect[0] + i.rect[2] for i in line)
        y1 = max(i.rect[1] + i.rect[3] for i in line)
        text = " ".join(i.text for i in line)
        merged.append(OcrItem((x0, y0, x1 - x0, y1 - y0), text, min(i.confidence for i in line)))
    return merged


class TestMergedOcr:
    def test_clock_box_covers_clock_digits(self, synthetic_match: SyntheticMatch) -> None:
        video = synthetic_match.video
        meta = probe_video(video)
        read = frame_reader(video, meta.width, meta.height)
        cfg = load_config(overrides=FAST).scoreboard
        result = locate_scorebox(read, meta.duration_s, meta.width, meta.height, cfg,
                                 read_ocr=lambda f: merge_lines(read_text(f)))
        assert result.found and result.clock_box is not None
        assert within_px(list(result.box), synthetic_match.schedule["scorebox_rect"])

        items = read_text(read(result.sample_time_s))
        digits = next(i.rect for i in items if find_clock(i.text))
        score = next(i.rect for i in items if find_goals(i.text))
        cx0, _, cx1, _ = edges(result.clock_box)
        dx0, _, dx1, _ = edges(digits)
        assert cx0 <= dx0 + 2 and dx1 - 2 <= cx1, (result.clock_box, digits)
        assert cx0 >= score[0] + score[2], "clock_box must not hide score changes"


class TestNoGraphic:
    def test_not_found_preview_saved_and_job_continues(self, videos, tmp_path: Path) -> None:
        db = tmp_path / "reel.db"
        init_db(db)
        video = videos["no_graphic"].video
        job = create_job(db, input_path=str(video))
        claim_next_job(db)
        paths = JobPaths(job.id, data_dir=tmp_path)
        ctx = PipelineContext(job_id=job.id, db_path=db, paths=paths, input_path=video,
                              config=load_config(overrides=FAST))
        after: list[str] = []
        stages = [
            Stage("ingest", 1.0, is_valid_ingest, run_ingest),
            Stage("locate_scorebox", 1.0, is_valid_locate_scorebox, run_locate_scorebox),
            Stage("next", 1.0, lambda c: False, lambda c: after.append("ran")),
        ]
        run_pipeline(ctx, stages)

        sb = read_model(paths.scorebox_json, Scorebox)
        assert sb.found is False and sb.box is None and sb.clock_box is None
        assert paths.scorebox_preview_jpg.is_file()
        assert after == ["ran"]
        assert get_job(db, job.id).status == "done"
