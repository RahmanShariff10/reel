"""Automatic score-box detection (pipeline stage 2: ``locate_scorebox``).

1. Sample frames spread across the match (skipping the start and end).
2. Full-frame OCR on each sample.
3. Keep text that looks like a cricket score (``145/3``) or overs (``16.2``).
4. Group candidates by screen position; merge an adjacent overs region.
5. Validate: present in enough samples, readings change plausibly over time.
6. Pick the best region, infer the runs/wickets order, grow the box to the
   surrounding score panel and pad it.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from reel.common.config import ScoreboardConfig
from reel.common.logging import get_logger
from reel.ingest.frames import grab_frame
from reel.scoreboard.ocr import OcrItem, read_text
from reel.scoreboard.parse import ScorePair, find_overs, find_pair, normalize

log = get_logger("scoreboard.locate")

Rect = tuple[int, int, int, int]  # x, y, w, h
FrameReader = Callable[[float], np.ndarray | None]
TextReader = Callable[[np.ndarray], list[OcrItem]]


@dataclass
class _Candidate:
    sample: int
    time_s: float
    item: OcrItem
    pair: ScorePair | None
    overs: float | None


@dataclass
class _Cluster:
    members: list[_Candidate] = field(default_factory=list)

    def median_rect(self) -> Rect:
        rects = [m.item.rect for m in self.members]
        return tuple(int(statistics.median(r[i] for r in rects)) for i in range(4))  # type: ignore[return-value]

    def accepts(self, rect: Rect) -> bool:
        cx, cy, cw, ch = self.median_rect()
        x, y, w, h = rect
        dx = abs((x + w / 2) - (cx + cw / 2))
        dy = abs((y + h / 2) - (cy + ch / 2))
        return dx <= 0.5 * max(w, cw) and dy <= 0.5 * max(h, ch)

    def per_sample(self) -> dict[int, _Candidate]:
        best: dict[int, _Candidate] = {}
        for m in self.members:
            if m.sample not in best or m.item.confidence > best[m.sample].item.confidence:
                best[m.sample] = m
        return best


@dataclass
class LocateResult:
    """Outcome of score-box detection."""

    found: bool
    box: Rect | None = None
    confidence: float = 0.0
    order: str | None = None
    sample_reading: str | None = None
    sample_time_s: float | None = None
    samples_read: int = 0


def sample_times(duration_s: float, cfg: ScoreboardConfig) -> list[float]:
    """Evenly spaced sample times, skipping the start and end of the video."""
    if duration_s <= 0:
        return []
    if duration_s >= cfg.short_video_min * 60:
        start, end = cfg.skip_start_min * 60, duration_s - cfg.skip_end_min * 60
    else:
        start, end = duration_s * cfg.short_skip_frac, duration_s * (1 - cfg.short_skip_frac)
    n = cfg.sample_frames
    step = (end - start) / n
    return [round(start + (i + 0.5) * step, 3) for i in range(n)]


def _cluster(cands: list[_Candidate]) -> list[_Cluster]:
    clusters: list[_Cluster] = []
    for c in cands:
        target = next((cl for cl in clusters if cl.accepts(c.item.rect)), None)
        if target is None:
            target = _Cluster()
            clusters.append(target)
        target.members.append(c)
    return clusters


def infer_order(pairs: list[ScorePair]) -> str | None:
    """Decide which number is runs: a value > 10 can't be wickets, else faster growth."""
    firsts = [p.first for p in pairs]
    seconds = [p.second for p in pairs]
    if max(firsts) > 10 and max(seconds) > 10:
        return None
    if max(seconds) <= 10 < max(firsts):
        return "runs-wickets"
    if max(firsts) <= 10 < max(seconds):
        return "wickets-runs"

    def growth(values: list[int]) -> int:
        return sum(max(0, b - a) for a, b in zip(values, values[1:]))

    return "wickets-runs" if growth(seconds) > growth(firsts) else "runs-wickets"


def plausibility(pairs: list[ScorePair], order: str) -> float:
    """Fraction of consecutive readings whose change is plausible for a cricket score."""
    if len(pairs) < 2:
        return 1.0
    seq = [(p.first, p.second) if order == "runs-wickets" else (p.second, p.first) for p in pairs]
    ok = 0
    for (r1, w1), (r2, w2) in zip(seq, seq[1:]):
        normal = r2 >= r1 and w1 - 1 <= w2 <= 10  # w1 - 1 allows a DRS reversal
        new_innings = r2 < r1 and w2 <= 2 and r2 <= 60
        ok += normal or new_innings
    return ok / (len(seq) - 1)


def _adjacent(a: Rect, b: Rect) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    overlap = min(ay + ah, by + bh) - max(ay, by)
    if overlap < 0.5 * min(ah, bh):
        return False
    gap = max(bx - (ax + aw), ax - (bx + bw))
    return gap <= 3 * max(ah, bh)


def _union(a: Rect, b: Rect) -> Rect:
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)


def grow_to_panel(img: np.ndarray, rect: Rect, tol: float = 30.0) -> Rect:
    """Grow a text rect outwards over the uniform panel colour surrounding it."""
    h_img, w_img = img.shape[:2]
    x, y, w, h = rect
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + w, w_img), min(y + h, h_img)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return rect
    band = max(2, h // 8)
    left = img[y0:y1, max(x0 - 2 * band, 0):max(x0 - band, 1)]
    right = img[y0:y1, min(x1 + band, w_img - 1):min(x1 + 2 * band, w_img)]
    if left.size == 0 or right.size == 0:
        return rect
    ref_l = np.median(left.reshape(-1, 3), axis=0)
    ref_r = np.median(right.reshape(-1, 3), axis=0)
    if np.abs(ref_l - ref_r).max() > tol:
        return rect  # no uniform panel around the text
    ref = (ref_l + ref_r) / 2

    def matches(strip: np.ndarray) -> bool:
        if strip.size == 0:
            return False
        close = np.abs(strip.reshape(-1, 3).astype(float) - ref).max(axis=1) <= tol
        return bool(close.mean() >= 0.9)

    max_x, max_y = w, h  # cap growth per side
    gx0 = x0
    while gx0 > 0 and x0 - gx0 < max_x and matches(img[y0:y1, gx0 - 1:gx0]):
        gx0 -= 1
    gx1 = x1
    while gx1 < w_img and gx1 - x1 < max_x and matches(img[y0:y1, gx1:gx1 + 1]):
        gx1 += 1
    gy0 = y0
    while gy0 > 0 and y0 - gy0 < max_y and matches(img[gy0 - 1:gy0, gx0:gx1]):
        gy0 -= 1
    gy1 = y1
    while gy1 < h_img and gy1 - y1 < max_y and matches(img[gy1:gy1 + 1, gx0:gx1]):
        gy1 += 1
    return (gx0, gy0, gx1 - gx0, gy1 - gy0)


def pad_rect(rect: Rect, frac: float, width: int, height: int) -> Rect:
    x, y, w, h = rect
    pad = max(2, round(frac * h))
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(width, x + w + pad), min(height, y + h + pad)
    return (x0, y0, x1 - x0, y1 - y0)


def locate_scorebox(
    read_frame: FrameReader,
    duration_s: float,
    width: int,
    height: int,
    cfg: ScoreboardConfig,
    read_ocr: TextReader = read_text,
    progress: Callable[[float], None] | None = None,
) -> LocateResult:
    """Find the score box. ``read_frame(t)`` returns a BGR frame at ``t`` seconds."""
    times = sample_times(duration_s, cfg)
    score_cands: list[_Candidate] = []
    overs_cands: list[_Candidate] = []
    samples_read = 0

    for i, t in enumerate(times):
        frame = read_frame(t)
        if frame is not None:
            samples_read += 1
            for item in read_ocr(frame):
                pair, overs = find_pair(item.text), find_overs(item.text)
                cand = _Candidate(i, t, item, pair, overs)
                if pair is not None:
                    score_cands.append(cand)
                elif overs is not None:
                    overs_cands.append(cand)
        if progress:
            progress((i + 1) / max(len(times), 1))

    if samples_read == 0:
        return LocateResult(found=False)

    best: tuple[int, _Cluster, str, float] | None = None
    for cluster in _cluster(score_cands):
        readings = sorted(cluster.per_sample().values(), key=lambda c: c.sample)
        presence = len(readings) / samples_read
        if presence < cfg.min_valid_ratio:
            continue
        pairs = [c.pair for c in readings if c.pair is not None]
        order = infer_order(pairs)
        if order is None:
            continue
        plaus = plausibility(pairs, order)
        if plaus < cfg.plausibility_ratio:
            continue
        log.info("Score-box candidate at %s: presence %.2f, plausibility %.2f",
                 cluster.median_rect(), presence, plaus)
        if best is None or len(readings) > best[0]:
            best = (len(readings), cluster, order, round(min(1.0, presence * plaus), 3))

    if best is None:
        return LocateResult(found=False, samples_read=samples_read)

    _, cluster, order, confidence = best
    rect = cluster.median_rect()
    overs_text: dict[int, str] = {}
    for oc in _cluster(overs_cands):
        if len(oc.per_sample()) / samples_read >= cfg.min_valid_ratio and _adjacent(
            rect, oc.median_rect()
        ):
            rect = _union(rect, oc.median_rect())
            overs_text = {s: c.item.text for s, c in oc.per_sample().items()}
            break

    readings = cluster.per_sample()
    mid = len(times) / 2
    sample = min(readings.values(), key=lambda c: abs(c.sample - mid))
    reading = normalize(" ".join(filter(None, [sample.item.text, overs_text.get(sample.sample)])))

    frame = read_frame(sample.time_s)
    if frame is not None:
        rect = grow_to_panel(frame, rect)
    rect = pad_rect(rect, cfg.box_padding_frac, width, height)

    return LocateResult(
        found=True,
        box=rect,
        confidence=confidence,
        order=order,
        sample_reading=reading,
        sample_time_s=sample.time_s,
        samples_read=samples_read,
    )


def frame_reader(video: Path | str, width: int, height: int) -> FrameReader:
    """Frame reader backed by ffmpeg seeking."""
    return lambda t: grab_frame(video, t, width, height)
