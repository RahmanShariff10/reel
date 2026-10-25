"""Thin wrapper around RapidOCR (PaddleOCR PP-OCR models on ONNX Runtime)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy as np


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


def read_text(image: np.ndarray) -> list[OcrItem]:
    """Detect and recognise all text lines in a BGR image."""
    result, _ = _engine()(image)
    items: list[OcrItem] = []
    for points, text, score in result or []:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x0, y0 = int(min(xs)), int(min(ys))
        items.append(
            OcrItem(
                rect=(x0, y0, int(max(xs)) - x0, int(max(ys)) - y0),
                text=str(text),
                confidence=float(score),
            )
        )
    return items
