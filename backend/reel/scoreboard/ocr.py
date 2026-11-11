"""Thin wrapper around RapidOCR (PaddleOCR PP-OCR models on ONNX Runtime).

- ``read_text``: whole frames, with RapidOCR's defaults.
- ``read_crop_text``: small score-box crops. RapidOCR's default detector scales an image until
  its *shortest* side is 736 px, which blows a 30 px crop up about 24 times: slow (~0.4 s) and,
  on real broadcasts, it misread zeros in most crops of one match. Enlarging the crop 3 times
  and capping the *longest* side instead read 173 of 180 sampled real crops right, none wrong,
  at ~0.09 s (F2 sprint notes).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import cv2
import numpy as np

CROP_SCALE = 3
CROP_DET_MAX_SIDE = 960


@dataclass(frozen=True)
class OcrItem:
    """One recognised text line: axis-aligned rect [x, y, w, h], text and confidence."""

    rect: tuple[int, int, int, int]
    text: str
    confidence: float


@lru_cache(maxsize=1)
def _engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


@lru_cache(maxsize=1)
def _crop_engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR(det_limit_type="max", det_limit_side_len=CROP_DET_MAX_SIDE)


def _items(result: Any, scale: float = 1.0) -> list[OcrItem]:
    items: list[OcrItem] = []
    for points, text, score in result or []:
        xs = [p[0] / scale for p in points]
        ys = [p[1] / scale for p in points]
        x0, y0 = int(min(xs)), int(min(ys))
        items.append(
            OcrItem(
                rect=(x0, y0, int(max(xs)) - x0, int(max(ys)) - y0),
                text=str(text),
                confidence=float(score),
            )
        )
    return items


def read_text(image: np.ndarray) -> list[OcrItem]:
    """Detect and recognise all text lines in a BGR image."""
    result, _ = _engine()(image)
    return _items(result)


def read_crop_text(image: np.ndarray) -> list[OcrItem]:
    """Read a small score-box crop; rects are in the crop's own pixels."""
    big = cv2.resize(image, None, fx=CROP_SCALE, fy=CROP_SCALE, interpolation=cv2.INTER_CUBIC)
    result, _ = _crop_engine()(big)
    return _items(result, CROP_SCALE)
