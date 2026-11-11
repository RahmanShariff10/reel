"""Read the score crops into raw readings (first half of stage 4, ``read_score``).

See "Goal state machine (stage 4)" in ARCHITECTURE.md.

- A crop is OCR'd only if its pixels outside ``clock_box`` changed since the last OCR'd crop,
  so a ticking clock alone never triggers OCR. Without a ``clock_box`` (a manually drawn
  box) the whole crop is compared. Crops are blurred first and the padding border (live
  video) is ignored, so compression flicker on real broadcasts doesn't count as a change.
- Change-triggered OCR runs at most every ``OCR_MIN_GAP_S``. Some graphics are see-through,
  so their crops change all the time, and while the graphic is hidden the crop is live video.
  A crop that matches the last visible crop again is OCR'd at once: the graphic is back, and
  its clock starts a new stretch.
- Every ``clock_read_s`` a crop is OCR'd anyway to read the clock. OCR always sees the whole
  score box, never a crop of only the clock, which RapidOCR splits (``45:0`` and ``3``).
- The clock is interpolated between reads within one unbroken stretch of the graphic being
  visible, never across a gap such as half-time, so every visible reading has ``clock_s``.
- A crop with neither score nor clock is ``visible: false``. A visible crop whose score can't
  be read is read again with the other OCR setting; if that fails too it is visible with
  ``home``/``away`` null: unreadable, not hidden.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from reel.common.config import ScoreboardConfig
from reel.common.logging import get_logger
from reel.common.models import ScoreReading
from reel.ingest.scan import crop_time
from reel.scoreboard.locate import clock_advances
from reel.scoreboard.ocr import OcrItem, read_crop_text, read_text
from reel.scoreboard.parse import parse_score

log = get_logger("scoreboard.read")

TextReader = Callable[[np.ndarray], list[OcrItem]]
Rect = tuple[int, int, int, int]  # x, y, w, h

OCR_MIN_GAP_S = 2.0  # change-triggered OCR runs at most this often
BLUR_PX = 5  # crops are blurred before comparing, which removes compression flicker


@dataclass
class ReadStats:
    crops: int = 0
    ocr_calls: int = 0
    clock_reads: int = 0  # OCR calls made only because a clock reading was due


def border(crop_height: int, cfg: ScoreboardConfig) -> int:
    """Width of the padding locate adds around the graphic, which shows live video."""
    return max(2, math.ceil(cfg.box_padding_frac * crop_height)) + 1


def crop_changed(
    a: np.ndarray,
    b: np.ndarray,
    cfg: ScoreboardConfig,
    ignore: Rect | None = None,
    margin: int = 0,
) -> bool:
    """True if enough pixels differ clearly (one changed digit counts, noise doesn't).

    Pixels inside ``ignore`` (the clock) and within ``margin`` of the edge never count.
    """
    if a.shape != b.shape:
        return True
    a, b = cv2.GaussianBlur(a, (BLUR_PX, BLUR_PX), 0), cv2.GaussianBlur(b, (BLUR_PX, BLUR_PX), 0)
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    if ignore is not None:
        x, y, w, h = ignore
        diff[max(0, y) : y + h, max(0, x) : x + w] = 0
    if margin > 0:
        diff[:margin, :] = 0
        diff[-margin:, :] = 0
        diff[:, :margin] = 0
        diff[:, -margin:] = 0
    return float((diff > cfg.crop_pixel_delta).mean()) > cfg.crop_change_frac


def in_reading_order(items: Sequence[OcrItem]) -> list[OcrItem]:
    """Lines top to bottom, each left to right. Items on a line overlap vertically; bucketing by
    pixel row instead split a real line when one item sat 1 px higher (``OEMP MIL 0 1``).
    """
    lines: list[tuple[float, float, list[OcrItem]]] = []
    for item in sorted(items, key=lambda i: i.rect[1] + i.rect[3] / 2):
        centre, height = item.rect[1] + item.rect[3] / 2, item.rect[3]
        line = next((ln for ln in lines if abs(ln[0] - centre) <= 0.5 * max(ln[1], height)), None)
        if line is None:
            lines.append((centre, height, [item]))
        else:
            line[2].append(item)
    return [i for _, _, members in lines for i in sorted(members, key=lambda i: i.rect[0])]


def reading_from(time_s: float, items: Sequence[OcrItem], cfg: ScoreboardConfig) -> ScoreReading:
    """One reading from the OCR items of a whole score-box crop, in reading order."""
    text = " ".join(i.text for i in in_reading_order(items))
    parsed = parse_score(text, cfg.score_max)
    confidence = float(np.mean([i.confidence for i in items])) if items else 0.0
    return ScoreReading(
        time_s=time_s,
        raw_text=text,
        home_code=parsed.home_code,
        away_code=parsed.away_code,
        home=parsed.home,
        away=parsed.away,
        clock_s=parsed.clock.seconds if parsed.clock else None,
        confidence=round(min(1.0, max(0.0, confidence)), 4),
        visible=parsed.home is not None or parsed.clock is not None,
    )


def clock_at(t: float, reads: Sequence[tuple[float, int]], cfg: ScoreboardConfig) -> int | None:
    """Match clock at ``t`` from clock reads ``(time_s, clock_s)`` sorted by time.

    Interpolates between two reads that agree with each other (the clock ran normally between
    them); otherwise counts on from the nearest read within ``clock_read_s``.
    """
    times = [r[0] for r in reads]
    i = bisect.bisect_right(times, t)
    before = reads[i - 1] if i > 0 else None
    after = reads[i] if i < len(reads) else None
    if before is not None and before[0] == t:
        return before[1]
    if before is not None and after is not None:
        dt, dclock = after[0] - before[0], after[1] - before[1]
        if dt <= 2 * cfg.clock_read_s and clock_advances(dt, dclock, cfg):
            return round(before[1] + (t - before[0]) * dclock / dt)
    near = [r for r in (before, after) if r is not None and abs(r[0] - t) <= cfg.clock_read_s]
    if not near:
        return None
    t0, c0 = min(near, key=lambda r: abs(r[0] - t))
    return max(0, round(c0 + (t - t0)))


def read_crops(
    crop_paths: Sequence[Path],
    clock_box: Rect | None,
    cfg: ScoreboardConfig,
    read_ocr: TextReader = read_crop_text,
    fallback_ocr: TextReader = read_text,
    progress: Callable[[float], None] | None = None,
) -> tuple[list[ScoreReading], ReadStats]:
    """Read every crop, OCR-ing only when the score area changed or a clock read is due.

    ``clock_box`` is in crop coordinates. ``fallback_ocr`` re-reads a visible crop whose score
    ``read_ocr`` couldn't read: the two settings fail on different broadcasts.
    """
    paths = sorted(crop_paths, key=crop_time)
    stats = ReadStats(crops=len(paths))
    readings: list[tuple[ScoreReading, int]] = []  # with the visible stretch it belongs to
    clock_reads: dict[int, list[tuple[float, int]]] = {}
    stretch = 0
    last_img: np.ndarray | None = None  # the last OCR'd crop
    last: ScoreReading | None = None
    shown_img: np.ndarray | None = None  # the last crop that showed the graphic
    last_ocr_t = float("-inf")

    for n, path in enumerate(paths):
        t = crop_time(path)
        img = cv2.imread(str(path))
        if img is None:
            continue
        margin = border(img.shape[0], cfg)
        changed = last_img is None or crop_changed(last_img, img, cfg, clock_box, margin)
        due = t - last_ocr_t >= cfg.clock_read_s
        if changed and t - last_ocr_t < OCR_MIN_GAP_S:
            hidden = last is not None and not last.visible
            back = hidden and shown_img is not None and not crop_changed(
                shown_img, img, cfg, clock_box, margin
            )
            changed = back  # too soon after the last OCR, unless the graphic just came back

        if last is None or changed or due:
            stats.ocr_calls += 1
            stats.clock_reads += not changed and last is not None
            was_visible = last is not None and last.visible
            last = reading_from(t, read_ocr(img), cfg)
            if last.visible and last.home is None:
                stats.ocr_calls += 1
                retry = reading_from(t, fallback_ocr(img), cfg)
                if retry.home is not None:
                    last = retry
            last_img, last_ocr_t = img, t
            if last.visible:
                shown_img = img
                stretch += not was_visible
                if last.clock_s is not None:
                    clock_reads.setdefault(stretch, []).append((t, last.clock_s))
        readings.append((last.model_copy(update={"time_s": t}), stretch))
        if progress and n % 50 == 0:
            progress(n / max(len(paths), 1))

    out = [
        r.model_copy(update={"clock_s": clock_at(r.time_s, clock_reads.get(s, []), cfg)})
        if r.visible
        else r.model_copy(update={"clock_s": None})
        for r, s in readings
    ]
    log.info(
        "Read %d crops with %d OCR calls (%d for the clock)",
        stats.crops, stats.ocr_calls, stats.clock_reads,
    )
    return out, stats


def read_job_crops(
    ctx, progress: Callable[[float], None] | None = None
) -> tuple[list[ScoreReading], ReadStats]:
    """Read a job's score crops and write ``score_readings.json`` (empty if no score box)."""
    from reel.common.models import Scorebox, read_model, write_model

    paths = ctx.paths
    scorebox = read_model(paths.scorebox_json, Scorebox)
    readings: list[ScoreReading] = []
    stats = ReadStats()
    if scorebox.found and scorebox.box:
        clock_box = None
        if scorebox.clock_box:
            bx, by = scorebox.box[0], scorebox.box[1]
            cx, cy, cw, ch = scorebox.clock_box
            clock_box = (cx - bx, cy - by, cw, ch)
        crops = list(paths.score_crops_dir.glob("crop_*.png"))
        readings, stats = read_crops(crops, clock_box, ctx.config.scoreboard, progress=progress)
    write_model(paths.score_readings_json, readings)
    return readings, stats
