"""Tests for slice-40-score-clock-read.

Acceptance criteria:
- A ticking graphic with an unchanged score: at most 1 OCR call per 30 s of video for the
  score, plus clock reads.
- A score change: the changed crop is OCR'd within one crop.
- "ARS 1-0 CHE", "ARS 1 0 CHE", "RMA 0 | 0 BAR" and "MCI 2:1 LIV 67:05" parse correctly.
- OCR items ['ARS', '1-0', 'CHE', '34:14'] read as home 1, away 0, clock 34:14.
- A hidden graphic reads as visible: false.

Also from the build order: no clock_box means the whole crop is compared (fix D), and real
broadcasts' letter-O zeros parse or count as unreadable (fix H).
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from reel.common.config import ScoreboardConfig
from reel.common.models import ScoreReading, read_model
from reel.ingest.scan import crop_name
from reel.jobs.pipeline import PipelineContext
from reel.scoreboard.ocr import OcrItem, read_crop_text, read_text
from reel.scoreboard.parse import find_goals, parse_score
from reel.scoreboard.read import (
    OCR_MIN_GAP_S,
    border,
    clock_at,
    crop_changed,
    in_reading_order,
    read_crops,
    read_job_crops,
    reading_from,
)
from tests.fixtures.make_football import clock_seconds_at, score_text_at

CFG = ScoreboardConfig()


class TestParseScore:
    @pytest.mark.parametrize(
        ("text", "home", "away", "codes", "clock"),
        [
            ("ARS 1-0 CHE", 1, 0, ("ARS", "CHE"), None),
            ("ARS 1 0 CHE", 1, 0, ("ARS", "CHE"), None),
            ("RMA 0 | 0 BAR", 0, 0, ("RMA", "BAR"), None),
            ("MCI 2:1 LIV 67:05", 2, 1, ("MCI", "LIV"), 67 * 60 + 5),
            # Read from real broadcasts in slice 39 (F2 sprint notes)
            ("MILO-0EMP22:43", 0, 0, ("MIL", "EMP"), 22 * 60 + 43),
            ("09:35 ELC O-ORMA", 0, 0, ("ELC", "RMA"), 9 * 60 + 35),
            ("OM 23PARISSG", 2, 3, ("OM", "PARISSG"), None),
            ("OM OO PARIS SG", 0, 0, ("OM", "PARIS"), None),
            ("OM 0 O PARIS SG", 0, 0, ("OM", "PARIS"), None),
        ],
    )
    def test_parses(self, text, home, away, codes, clock) -> None:
        parsed = parse_score(text)
        assert (parsed.home, parsed.away) == (home, away)
        assert (parsed.home_code, parsed.away_code) == codes
        assert (parsed.clock.seconds if parsed.clock else None) == clock

    @pytest.mark.parametrize("text", ["OM O PARIS SG", "OM PARIS SG 36:03", "", "SKY SPORTS"])
    def test_no_score(self, text: str) -> None:
        parsed = parse_score(text)
        assert parsed.home is None and parsed.away is None


def line(*texts: str, y: int = 10) -> list[OcrItem]:
    x, items = 5, []
    for text in texts:
        items.append(OcrItem((x, y, 12 * len(text), 24), text, 0.9))
        x += 12 * len(text) + 8
    return items


class TestReading:
    def test_separate_items(self) -> None:
        r = reading_from(12.5, line("ARS", "1-0", "CHE", "34:14"), CFG)
        assert r.visible and (r.home, r.away) == (1, 0)
        assert (r.home_code, r.away_code) == ("ARS", "CHE")
        assert r.clock_s == 34 * 60 + 14 and r.time_s == 12.5

    def test_order_follows_the_screen_not_the_ocr(self) -> None:
        items = line("ARS", "1-0", "CHE", "34:14")
        r = reading_from(0.0, list(reversed(items)), CFG)
        assert (r.home, r.away, r.home_code) == (1, 0, "ARS")

    def test_items_a_pixel_apart_stay_on_one_line(self) -> None:
        # Seen on a real broadcast: row bucketing put "OEMP" first and read 0-1.
        items = [
            OcrItem((5, 10, 40, 18), "MIL", 0.9),
            OcrItem((50, 10, 10, 18), "0", 0.9),
            OcrItem((65, 9, 60, 18), "OEMP", 0.9),
        ]
        assert [i.text for i in in_reading_order(items)] == ["MIL", "0", "OEMP"]
        stacked = [
            OcrItem((5, 40, 60, 18), "ARS 1-0 CHE", 0.9),
            OcrItem((5, 10, 50, 18), "34:14", 0.9),
        ]
        assert [i.text for i in in_reading_order(stacked)] == ["34:14", "ARS 1-0 CHE"]

    def test_hidden_graphic(self) -> None:
        r = reading_from(0.0, [], CFG)
        assert r.visible is False and r.home is None and r.clock_s is None

    def test_clock_without_a_readable_score_is_unreadable_not_hidden(self) -> None:
        r = reading_from(0.0, line("OM", "O PARIS SG", "36:03"), CFG)
        assert r.visible is True and r.home is None and r.away is None
        assert r.clock_s == 36 * 60 + 3


class TestChangeDetection:
    def test_noise_ignored_digit_change_detected(self) -> None:
        a = np.zeros((50, 300, 3), np.uint8)
        noisy = a + np.random.default_rng(0).integers(0, 8, a.shape, dtype=np.uint8)
        assert not crop_changed(a, noisy, CFG)
        digit = a.copy()
        digit[15:35, 100:112] = 255  # one digit-sized change
        assert crop_changed(a, digit, CFG)

    def test_compression_flicker_ignored(self) -> None:
        # Real broadcasts flicker by tens of levels at single pixels around small text.
        rng = np.random.default_rng(1)
        a = np.full((30, 260, 3), 40, np.uint8)
        flicker = a.copy()
        ys, xs = rng.integers(0, 30, 150), rng.integers(0, 260, 150)
        flicker[ys, xs] = 120
        assert not crop_changed(a, flicker, CFG)
        digit = a.copy()
        digit[8:24, 100:110] = 255
        assert crop_changed(a, digit, CFG)

    def test_changes_inside_the_clock_box_are_ignored(self) -> None:
        a = np.zeros((50, 300, 3), np.uint8)
        tick = a.copy()
        tick[15:35, 250:262] = 255
        assert crop_changed(a, tick, CFG)
        assert not crop_changed(a, tick, CFG, ignore=(240, 5, 55, 40))

    def test_live_video_in_the_padding_is_ignored(self) -> None:
        a = np.zeros((50, 300, 3), np.uint8)
        cut = a.copy()
        cut[:4, :] = cut[-4:, :] = 200  # a camera cut behind the box's padding
        cut[:, :4] = cut[:, -4:] = 200
        margin = border(50, CFG)
        assert margin >= 4
        assert crop_changed(a, cut, CFG)
        assert not crop_changed(a, cut, CFG, margin=margin)


class TestFallback:
    def test_unreadable_score_is_read_again_with_the_other_setting(self, tmp_path: Path) -> None:
        cv2.imwrite(str(tmp_path / crop_name(0.0)), np.zeros((CROP_H, CROP_W, 3), np.uint8))
        calls: list[str] = []

        def first(img: np.ndarray) -> list[OcrItem]:
            calls.append("first")
            return line("ARS", "61-1", "CHE", "45:33")  # a misread: 61 goals can't be right

        def fallback(img: np.ndarray) -> list[OcrItem]:
            calls.append("fallback")
            return line("ARS", "1-1", "CHE", "45:33")

        readings, stats = read_crops([tmp_path / crop_name(0.0)], CLOCK_BOX, CFG,
                                     read_ocr=first, fallback_ocr=fallback)
        assert calls == ["first", "fallback"] and stats.ocr_calls == 2
        assert (readings[0].home, readings[0].away) == (1, 1)

    def test_readable_score_needs_no_fallback(self, tmp_path: Path) -> None:
        cv2.imwrite(str(tmp_path / crop_name(0.0)), np.zeros((CROP_H, CROP_W, 3), np.uint8))

        def fallback(img: np.ndarray) -> list[OcrItem]:
            raise AssertionError("not needed")

        readings, _ = read_crops([tmp_path / crop_name(0.0)], CLOCK_BOX, CFG,
                                 read_ocr=lambda img: line("ARS", "1-0", "CHE", "45:33"),
                                 fallback_ocr=fallback)
        assert readings[0].home == 1


class TestClockAt:
    reads = [(10.0, 1800), (40.0, 1830), (70.0, 1860), (140.0, 2700), (170.0, 2730)]

    def test_interpolates_between_agreeing_reads(self) -> None:
        assert clock_at(25.0, self.reads, CFG) == 1815
        assert clock_at(40.0, self.reads, CFG) == 1830

    def test_counts_on_from_the_nearest_read_when_reads_disagree(self) -> None:
        assert clock_at(80.0, self.reads, CFG) == 1870
        assert clock_at(130.0, self.reads, CFG) == 2690
        assert clock_at(105.0, self.reads, CFG) is None  # more than 30 s from any read

    def test_no_reads(self) -> None:
        assert clock_at(5.0, [], CFG) is None


# ---------------------------------------------------------------------------
# Drawn crops, read with real OCR
# ---------------------------------------------------------------------------

CROP_W, CROP_H = 320, 50
CLOCK_BOX = (205, 0, 115, 50)  # in crop coordinates


PAD = 4  # like locate's padding: a border of live video around the panel


def draw(score: str | None, clock_s: int, rng: np.random.Generator) -> np.ndarray:
    """A score graphic crop, or live video behind a hidden graphic when ``score`` is None."""
    video = rng.integers(0, 255, (CROP_H, CROP_W, 3), dtype=np.uint8)
    if score is None:
        return video
    img = video.copy()
    img[PAD:-PAD, PAD:-PAD] = (42, 27, 13)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, score, (10, 34), font, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    clock = f"{clock_s // 60:02d}:{clock_s % 60:02d}"
    cv2.putText(img, clock, (215, 34), font, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def write_crops(tmp: Path, timeline) -> list[Path]:
    """``timeline(t)`` gives (score text or None, clock seconds) for each crop at 2 fps."""
    rng = np.random.default_rng(0)
    paths = []
    for i in range(int(timeline.duration_s * 2)):
        t = i / 2
        score, clock = timeline(t)
        path = tmp / crop_name(t)
        cv2.imwrite(str(path), draw(score, clock, rng))
        paths.append(path)
    return paths


class CountingOcr:
    """Real OCR, both settings, counting every call."""

    def __init__(self) -> None:
        self.calls = 0

    def _count(self, fn):
        def read(img: np.ndarray) -> list[OcrItem]:
            self.calls += 1
            return fn(img)

        return read

    def options(self) -> dict:
        return {"read_ocr": self._count(read_crop_text), "fallback_ocr": self._count(read_text)}


class Ticking:
    """5 minutes of a ticking clock; the score changes once, at 200 s."""

    duration_s = 300.0
    change_s = 200.0

    def __call__(self, t: float) -> tuple[str, int]:
        return ("ARS 1-0 CHE" if t < self.change_s else "ARS 2-0 CHE"), 1800 + int(t)


@pytest.fixture(scope="module")
def ticking(tmp_path_factory: pytest.TempPathFactory):
    crops = write_crops(tmp_path_factory.mktemp("ticking"), Ticking())
    ocr = CountingOcr()
    readings, stats = read_crops(crops, CLOCK_BOX, CFG, **ocr.options())
    return readings, stats, ocr


class TestOcrSkipping:
    def test_unchanged_score_needs_only_clock_reads(self, ticking) -> None:
        readings, stats, ocr = ticking
        assert stats.ocr_calls == ocr.calls
        score_calls = stats.ocr_calls - stats.clock_reads
        assert score_calls == 2  # the first crop and the score change
        assert score_calls <= Ticking.duration_s / 30
        assert stats.clock_reads <= Ticking.duration_s / CFG.clock_read_s + 1

    def test_score_change_read_on_the_changed_crop(self, ticking) -> None:
        readings, _, _ = ticking
        by_time = {r.time_s: r for r in readings}
        assert by_time[Ticking.change_s - 0.5].home == 1
        assert by_time[Ticking.change_s].home == 2

    def test_every_crop_has_score_codes_and_clock(self, ticking) -> None:
        readings, _, _ = ticking
        assert len(readings) == Ticking.duration_s * 2
        for r in readings:
            score, clock = Ticking()(r.time_s)
            assert r.visible and (r.home, r.away) == find_goals(score), r
            assert (r.home_code, r.away_code) == ("ARS", "CHE"), r
            assert r.clock_s is not None and abs(r.clock_s - clock) <= 1, r

    def test_without_clock_box_the_whole_crop_is_compared(self, tmp_path: Path) -> None:
        class Minute(Ticking):
            duration_s = 30.0

        crops = write_crops(tmp_path, Minute())
        ocr = CountingOcr()
        readings, stats = read_crops(crops, None, CFG, **ocr.options())
        # Every tick changes the crop, so OCR runs as often as the gap allows.
        assert stats.ocr_calls >= Minute.duration_s / OCR_MIN_GAP_S - 1
        assert all(r.clock_s is not None for r in readings)


class Hiding:
    """The graphic hides for 20 s (live video shows through), then returns unchanged."""

    duration_s = 60.0
    hidden = (20.0, 40.0)

    def __call__(self, t: float) -> tuple[str | None, int]:
        score = None if self.hidden[0] <= t < self.hidden[1] else "ARS 1-0 CHE"
        return score, 1800 + int(t)


class TestHiddenGraphic:
    def test_hidden_is_not_visible_and_ocr_is_limited(self, tmp_path: Path) -> None:
        crops = write_crops(tmp_path, Hiding())
        ocr = CountingOcr()
        readings, stats = read_crops(crops, CLOCK_BOX, CFG, **ocr.options())
        h0, h1 = Hiding.hidden
        inside = [r for r in readings if h0 <= r.time_s < h1]
        assert inside and all(not r.visible and r.clock_s is None for r in inside)
        after = [r for r in readings if r.time_s >= h1]
        assert all(r.visible and (r.home, r.away) == (1, 0) for r in after)
        assert stats.ocr_calls <= (h1 - h0) / OCR_MIN_GAP_S + Hiding.duration_s / 30 + 3


# ---------------------------------------------------------------------------
# The synthetic football broadcast, end to end
# ---------------------------------------------------------------------------

# A crop named t shows the latest frame before t + 0.25 s (scan's fps filter), so crops this
# close to a scheduled change, on either side, can show either state.
EDGE_S = 0.6
LATE_S = OCR_MIN_GAP_S + 0.6  # a change right after another OCR call is read this late


def settled(schedule: dict, t: float) -> bool:
    changes = [c["time_s"] for c in schedule["score_changes"]]
    starts = [h0 for h0, _ in schedule["hidden_intervals"]]
    ends = [h1 for _, h1 in schedule["hidden_intervals"]]
    return (
        all(not (-EDGE_S < t - c < LATE_S) for c in changes + starts + ends)
    )


@pytest.fixture(scope="module")
def job_readings(scanned_match: PipelineContext):
    return read_job_crops(scanned_match)


class TestSyntheticBroadcast:
    def test_visible_crops_read_score_and_clock(self, job_readings, synthetic_match) -> None:
        readings, _ = job_readings
        s = synthetic_match.schedule
        visible = [r for r in readings if score_text_at(s, r.time_s) and settled(s, r.time_s)]
        assert len(visible) > 180
        right = [r for r in visible if (r.home, r.away) == find_goals(score_text_at(s, r.time_s))]
        assert len(right) / len(visible) >= 0.98
        ticking = [r for r in visible
                   if r.clock_s is not None
                   and abs(r.clock_s - clock_seconds_at(s, r.time_s)) <= 1]
        assert len(ticking) / len(visible) >= 0.98

    def test_hidden_crops_not_visible(self, job_readings, synthetic_match) -> None:
        readings, _ = job_readings
        s = synthetic_match.schedule
        hidden = [r for r in readings if not score_text_at(s, r.time_s) and settled(s, r.time_s)]
        assert hidden
        assert sum(not r.visible for r in hidden) / len(hidden) >= 0.95

    def test_ocr_on_few_crops(self, job_readings) -> None:
        readings, stats = job_readings
        assert stats.crops == len(readings)
        assert stats.ocr_calls / stats.crops < 0.25

    def test_second_half_clock_after_half_time(self, job_readings, synthetic_match) -> None:
        readings, _ = job_readings
        s = synthetic_match.schedule
        start = s["halves"][1]["start_s"]
        first = [r for r in readings if start + LATE_S <= r.time_s < start + 10 and r.visible]
        assert first
        assert all(abs(r.clock_s - clock_seconds_at(s, r.time_s)) <= 1 for r in first)

    def test_writes_score_readings_json(self, job_readings, scanned_match) -> None:
        readings, _ = job_readings
        stored = read_model(scanned_match.paths.score_readings_json, list[ScoreReading])
        assert stored == readings
