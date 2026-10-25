"""Camera-cut detection on a stream of low-resolution frames (PySceneDetect)."""

from __future__ import annotations

import numpy as np
from scenedetect.detectors import ContentDetector


class CutDetector:
    """Feed frames one at a time; collects the frame indices where a new shot starts."""

    def __init__(self, fps: float, threshold: float = 27.0, min_shot_s: float = 0.5) -> None:
        self.fps = fps
        self._detector = ContentDetector(
            threshold=threshold, min_scene_len=max(1, round(min_shot_s * fps))
        )
        self.cut_frames: list[int] = []

    def process(self, frame_index: int, frame: np.ndarray) -> list[int]:
        """Process one BGR frame; returns frame indices of newly confirmed cuts.

        A cut can be confirmed a few frames after it happens, so returned indices may be
        earlier than ``frame_index``.
        """
        return self._record(self._detector.process_frame(frame_index, frame))

    def flush(self, last_index: int) -> list[int]:
        """Return cuts still pending at the end of the stream."""
        return self._record(self._detector.post_process(last_index))

    def _record(self, cuts: list[int]) -> list[int]:
        new = sorted(c for c in cuts if c > 0 and c not in self.cut_frames)
        self.cut_frames.extend(new)
        return new

    @property
    def cut_times(self) -> list[float]:
        return [round(c / self.fps, 3) for c in self.cut_frames]
