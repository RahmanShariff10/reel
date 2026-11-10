"""Automatic score-graphic detection (pipeline stage 2: ``locate_scorebox``).

The match clock is the anchor (see "Score-graphic detection" in ARCHITECTURE.md):

1. Sample frames spread across the match (skipping the start and end) and OCR each one.
2. Keep text containing a clock token and group it by screen position.
3. A position qualifies if it shows a clock in enough samples and the clock advances with
   the video (the linearity check). Static text such as a ``12:30`` caption fails it.
4. Find the score next to the clock, on the same line or the line above or below.
5. The box covers the clock and the score, grown to the surrounding panel and padded.
   ``clock_box`` covers the clock digits, also when OCR returns clock and score as one item.
"""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from reel.common.config import ScoreboardConfig
from reel.common.logging import get_logger
from reel.ingest.frames import grab_frame
from reel.scoreboard.ocr import OcrItem, read_text
from reel.scoreboard.parse import ClockToken, find_clock, find_goals

log = get_logger("scoreboard.locate")

Rect = tuple[int, int, int, int]  # x, y, w, h
FrameReader = Callable[[float], np.ndarray | None]
TextReader = Callable[[np.ndarray], list[OcrItem]]

CLOCK_RESOLUTION_S = 1.0  # clocks show whole seconds, so a reading can be up to 1 s off
NEIGHBOUR_X = 8.0  # the score may be this many text heights left or right of the clock
NEIGHBOUR_Y = 1.5  # ... or this many text heights above or below it
RUN_GAP = 2.0  # items closer than this many text heights belong to one run of text
CLOCK_PAIRS = 5  # frame pairs 1 s apart used to find the clock in merged OCR text
# Share of the clock's samples that must show a readable score beside it. The ticking clock
# already places the graphic; this only confirms it. Kept low because some fonts' zeros are
# often unreadable: a real 0-0 half gave a readable score in under 40% of samples.
SCORE_BESIDE_MIN = 0.2


@dataclass
class _Hit:
    """A clock token read at one sample."""

    sample: int
    time_s: float
    item: OcrItem
    clock: ClockToken


@dataclass
class _ScoreLine:
    """The clock and the score next to it, at one sample."""

    rect: Rect
    text: str
    merged: bool  # OCR returned the clock and the score as one item


@dataclass
class _Cluster:
    hits: list[_Hit] = field(default_factory=list)

    def median_rect(self) -> Rect:
        return _median_rect([h.item.rect for h in self.hits])

    def per_sample(self) -> list[_Hit]:
        """The most confident hit per sample, in time order."""
        best: dict[int, _Hit] = {}
        for hit in self.hits:
            if hit.sample not in best or hit.item.confidence > best[hit.sample].item.confidence:
                best[hit.sample] = hit
        return [best[s] for s in sorted(best)]


@dataclass
class LocateResult:
    """Outcome of score-graphic detection."""

    found: bool
    box: Rect | None = None
    clock_box: Rect | None = None
    confidence: float = 0.0
    sample_reading: str | None = None
    sample_time_s: float | None = None
    samples_read: int = 0
    presence: float = 0.0
    linearity: float = 0.0


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


def _median_rect(rects: Sequence[Rect]) -> Rect:
    return tuple(int(statistics.median(r[i] for r in rects)) for i in range(4))  # type: ignore[return-value]


def _same_place(rect: Rect, centre: Rect) -> bool:
    x, y, w, h = rect
    cx, cy, cw, ch = centre
    dx = abs((x + w / 2) - (cx + cw / 2))
    dy = abs((y + h / 2) - (cy + ch / 2))
    return dx <= 0.5 * max(w, cw) and dy <= 0.5 * max(h, ch)


def _cluster(hits: Sequence[_Hit]) -> list[_Cluster]:
    clusters: list[_Cluster] = []
    for hit in hits:
        target = next((c for c in clusters if _same_place(hit.item.rect, c.median_rect())), None)
        if target is None:
            target = _Cluster()
            clusters.append(target)
        target.hits.append(hit)
    return clusters


def clock_advances(dt: float, dclock: float, cfg: ScoreboardConfig) -> bool:
    """Whether the clock moved forward at 0.9–1.1x video time, allowing for whole seconds."""
    lo = cfg.clock_rate_min * dt - CLOCK_RESOLUTION_S
    hi = cfg.clock_rate_max * dt + CLOCK_RESOLUTION_S
    return dclock > 0 and lo <= dclock <= hi


def linearity(hits: Sequence[_Hit], cfg: ScoreboardConfig) -> float:
    """Share of consecutive samples whose clock advances with the video.

    Pairs across half-time fail; the rest of the pairs passing is what lets a real clock
    clear ``clock_linear_ratio``.
    """
    pairs = list(zip(hits, hits[1:]))
    if not pairs:
        return 0.0
    passed = sum(
        clock_advances(b.time_s - a.time_s, b.clock.seconds - a.clock.seconds, cfg)
        for a, b in pairs
    )
    return passed / len(pairs)


def _union(rects: Sequence[Rect]) -> Rect:
    x0 = min(r[0] for r in rects)
    y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects)
    y1 = max(r[1] + r[3] for r in rects)
    return (x0, y0, x1 - x0, y1 - y0)


def _gap(a: Rect, b: Rect) -> tuple[float, float]:
    """Horizontal and vertical gaps between two rects (0 when they overlap)."""
    gx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), 0)
    gy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]), 0)
    return gx, gy


def _same_line(a: Rect, b: Rect) -> bool:
    overlap = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return overlap >= 0.5 * min(a[3], b[3])


def _runs(items: Sequence[OcrItem], height: float) -> list[list[OcrItem]]:
    """Group items into runs of text: same line, left to right, small gaps."""
    runs: list[list[OcrItem]] = []
    for item in sorted(items, key=lambda i: (i.rect[1], i.rect[0])):
        run = next(
            (
                r
                for r in runs
                if _same_line(r[-1].rect, item.rect)
                and _gap(r[-1].rect, item.rect)[0] <= RUN_GAP * height
            ),
            None,
        )
        if run is None:
            runs.append([item])
        else:
            run.append(item)
            run.sort(key=lambda i: i.rect[0])
    return runs


def _text(items: Sequence[OcrItem]) -> str:
    return " ".join(i.text for i in sorted(items, key=lambda i: i.rect[0]))


def score_line(
    clock_item: OcrItem, items: Sequence[OcrItem], cfg: ScoreboardConfig
) -> _ScoreLine | None:
    """The score next to the clock, or None if there is none."""
    if find_goals(clock_item.text, cfg.score_max) is not None:
        return _ScoreLine(clock_item.rect, clock_item.text, merged=True)

    height = clock_item.rect[3]
    near = [
        i
        for i in items
        if i is not clock_item
        and _gap(clock_item.rect, i.rect)[0] <= NEIGHBOUR_X * height
        and _gap(clock_item.rect, i.rect)[1] <= NEIGHBOUR_Y * height
    ]
    scored = [r for r in _runs(near, height) if find_goals(_text(r), cfg.score_max)]
    if not scored:
        return None
    run = min(scored, key=lambda r: sum(_gap(clock_item.rect, _union([i.rect for i in r]))))
    rect = _union([clock_item.rect, *(i.rect for i in run)])
    return _ScoreLine(rect, _text([clock_item, *run]), merged=False)


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


def _clip(rect: Rect, outer: Rect) -> Rect:
    x0, y0 = max(rect[0], outer[0]), max(rect[1], outer[1])
    x1 = min(rect[0] + rect[2], outer[0] + outer[2])
    y1 = min(rect[1] + rect[3], outer[1] + outer[3])
    return (x0, y0, max(0, x1 - x0), max(0, y1 - y0))


def changing_columns(
    read_frame: FrameReader, times: Sequence[float], rect: Rect, cfg: ScoreboardConfig
) -> tuple[int, int] | None:
    """Columns of ``rect`` whose pixels change between frames 1 s apart in most pairs.

    That is the seconds digit of a running clock.
    """
    x, y, w, h = rect
    counts = np.zeros(w)
    pairs = 0
    for t in times:
        a, b = read_frame(t), read_frame(t + 1.0)
        if a is None or b is None:
            continue
        crop_a = a[y : y + h, x : x + w].astype(int)
        crop_b = b[y : y + h, x : x + w].astype(int)
        if crop_a.shape != crop_b.shape or crop_a.size == 0:
            continue
        changed = (np.abs(crop_a - crop_b).max(axis=2) > cfg.crop_pixel_delta).any(axis=0)
        counts[: changed.size] += changed
        pairs += 1
    if pairs == 0:
        return None
    cols = np.flatnonzero(counts / pairs >= cfg.clock_change_ratio)
    return (x + int(cols[0]), x + int(cols[-1])) if cols.size else None


def merged_clock_box(item: OcrItem, anchor: tuple[int, int] | None) -> Rect:
    """The clock's part of an OCR item that also holds the score.

    Its position in the text gives an estimate. The seconds digit, found from pixels that
    change every second, fixes the right edge, because a proportional font makes the estimate
    drift.
    """
    clock = find_clock(item.text)
    x, y, w, h = item.rect
    if clock is None or not item.text:
        return item.rect
    char_w = w / len(item.text)
    x0, x1 = x + clock.start * char_w, x + clock.end * char_w
    if anchor is not None and clock.added_min is None:
        x1 = max(x1, anchor[1] + 1)
        x0 = min(x0, x1 - (clock.end - clock.start) * char_w)
    x0, x1 = max(x, x0 - 0.5 * char_w), min(x + w, x1 + 0.5 * char_w)
    return (int(x0), y, int(round(x1 - x0)), h)


def locate_scorebox(
    read_frame: FrameReader,
    duration_s: float,
    width: int,
    height: int,
    cfg: ScoreboardConfig,
    read_ocr: TextReader = read_text,
    progress: Callable[[float], None] | None = None,
) -> LocateResult:
    """Find the score graphic. ``read_frame(t)`` returns a BGR frame at ``t`` seconds."""
    times = sample_times(duration_s, cfg)
    hits: list[_Hit] = []
    items_at: dict[int, list[OcrItem]] = {}

    for i, t in enumerate(times):
        frame = read_frame(t)
        if frame is not None:
            items_at[i] = read_ocr(frame)
            for item in items_at[i]:
                clock = find_clock(item.text)
                if clock is not None:
                    hits.append(_Hit(i, t, item, clock))
        if progress:
            progress((i + 1) / max(len(times), 1))

    samples_read = len(items_at)
    if samples_read == 0:
        return LocateResult(found=False)

    best: tuple[_Cluster, list[_Hit], dict[int, _ScoreLine], float, float] | None = None
    for cluster in _cluster(hits):
        per_sample = cluster.per_sample()
        presence = len(per_sample) / samples_read
        line = linearity(per_sample, cfg)
        if presence < cfg.min_valid_ratio or line < cfg.clock_linear_ratio:
            continue
        lines = {
            h.sample: s
            for h in per_sample
            if (s := score_line(h.item, items_at[h.sample], cfg)) is not None
        }
        beside = len(lines) / len(per_sample)
        log.info(
            "Clock candidate at %s: presence %.2f, linearity %.2f, score beside it %.2f",
            cluster.median_rect(), presence, line, beside,
        )
        if beside < SCORE_BESIDE_MIN:
            continue
        if best is None or len(per_sample) > len(best[1]):
            best = (cluster, per_sample, lines, presence, line)

    if best is None:
        return LocateResult(found=False, samples_read=samples_read)

    cluster, per_sample, lines, presence, line = best
    with_score = [h for h in per_sample if h.sample in lines]
    rect = _median_rect([lines[h.sample].rect for h in with_score])
    # The most typical sample, so stray text that OCR joined to the line stays out of it.
    sample = min(
        with_score, key=lambda h: sum(abs(a - b) for a, b in zip(lines[h.sample].rect, rect))
    )

    frame = read_frame(sample.time_s)
    if frame is not None:
        rect = grow_to_panel(frame, rect)
    box = pad_rect(rect, cfg.box_padding_frac, width, height)

    merged = sum(lines[h.sample].merged for h in with_score) > len(with_score) / 2
    if merged:
        anchor_times = [h.time_s for h in with_score][:: max(1, len(with_score) // CLOCK_PAIRS)]
        anchor = changing_columns(read_frame, anchor_times[:CLOCK_PAIRS], sample.item.rect, cfg)
        clock_rect = merged_clock_box(sample.item, anchor)
    else:
        clock_rect = _median_rect([h.item.rect for h in with_score])
    clock_box = _clip(pad_rect(clock_rect, cfg.box_padding_frac, width, height), box)

    return LocateResult(
        found=True,
        box=box,
        clock_box=clock_box,
        confidence=round(min(1.0, presence * line), 3),
        sample_reading=lines[sample.sample].text,
        sample_time_s=sample.time_s,
        samples_read=samples_read,
        presence=round(presence, 3),
        linearity=round(line, 3),
    )


def frame_reader(video: Path | str, width: int, height: int) -> FrameReader:
    """Frame reader backed by ffmpeg seeking."""
    return lambda t: grab_frame(video, t, width, height)
