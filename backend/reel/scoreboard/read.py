"""Read the score crops into raw readings (first half of stage 4, ``read_score``).

- Skip unchanged crops: if a crop barely differs from the last OCR'd crop, reuse
  that crop's reading instead of running OCR again.
- OCR changed crops with RapidOCR and parse runs, wickets, overs and team.
- A crop with no score in it is recorded as ``visible: false`` (box hidden).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from reel.common.config import ScoreboardConfig
from reel.common.logging import get_logger
from reel.common.models import ScoreReading
from reel.ingest.scan import crop_time
from reel.scoreboard.ocr import OcrItem, read_text
from reel.scoreboard.parse import parse_score

log = get_logger("scoreboard.read")

TextReader = Callable[[np.ndarray], list[OcrItem]]


@dataclass
class ReadStats:
    crops: int = 0
    ocr_calls: int = 0


def crop_changed(a: np.ndarray, b: np.ndarray, cfg: ScoreboardConfig) -> bool:
    """True if enough pixels differ clearly (a single changed digit counts, noise doesn't)."""
    if a.shape != b.shape:
        return True
    diff = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    return float((diff > cfg.crop_pixel_delta).mean()) > cfg.crop_change_frac


def _reading(time_s: float, items: list[OcrItem], order: str | None) -> ScoreReading:
    text = " ".join(i.text for i in sorted(items, key=lambda i: (i.rect[1] // 10, i.rect[0])))
    parsed = parse_score(text, order)
    confidence = float(np.mean([i.confidence for i in items])) if items else 0.0
    if parsed is None or parsed.runs is None:
        return ScoreReading(time_s=time_s, raw_text=text, visible=False, confidence=confidence,
                            overs=parsed.overs if parsed else None,
                            team=parsed.team if parsed else None)
    return ScoreReading(
        time_s=time_s, raw_text=text, runs=parsed.runs, wickets=parsed.wickets,
        overs=parsed.overs, team=parsed.team, confidence=round(confidence, 4), visible=True,
    )


def read_crops(
    crop_paths: list[Path],
    order: str | None,
    cfg: ScoreboardConfig,
    read_ocr: TextReader = read_text,
    progress: Callable[[float], None] | None = None,
) -> tuple[list[ScoreReading], ReadStats]:
    """OCR changed crops only; unchanged crops reuse the previous reading."""
    stats = ReadStats(crops=len(crop_paths))
    readings: list[ScoreReading] = []
    last_img: np.ndarray | None = None
    last: ScoreReading | None = None
    for n, path in enumerate(sorted(crop_paths, key=crop_time)):
        t = crop_time(path)
        img = cv2.imread(str(path))
        if img is None:
            continue
        same = last_img is not None and not crop_changed(last_img, img, cfg)
        if same and last is not None:
            readings.append(last.model_copy(update={"time_s": t}))
        else:
            stats.ocr_calls += 1
            last = _reading(t, read_ocr(img), order)
            last_img = img
            readings.append(last)
        if progress and n % 50 == 0:
            progress(n / max(len(crop_paths), 1))
    log.info("Read %d crops with %d OCR calls", stats.crops, stats.ocr_calls)
    return readings, stats


def read_job_crops(ctx, progress: Callable[[float], None] | None = None) -> list[ScoreReading]:
    """Read a job's score crops and write ``score_readings.json`` (empty if no score box)."""
    from reel.common.models import Scorebox, read_model, write_model

    paths = ctx.paths
    scorebox = read_model(paths.scorebox_json, Scorebox)
    readings: list[ScoreReading] = []
    if scorebox.found:
        crops = list(paths.score_crops_dir.glob("crop_*.png"))
        readings, _ = read_crops(crops, scorebox.order, ctx.config.scoreboard, progress=progress)
    write_model(paths.score_readings_json, readings)
    return readings
