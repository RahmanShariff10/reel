"""Single-frame extraction from a video with ffmpeg (fast input seeking)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from reel.ingest.probe import find_binary


def grab_frame(video: Path | str, t: float, width: int, height: int) -> np.ndarray | None:
    """Return the frame at ``t`` seconds as a BGR array, or None if it can't be read."""
    proc = subprocess.run(
        [
            find_binary("ffmpeg"), "-v", "error", "-ss", f"{max(t, 0.0):.3f}",
            "-i", str(video), "-frames:v", "1",
            "-f", "rawvideo", "-pix_fmt", "bgr24", "-",
        ],
        capture_output=True,
        check=False,
        timeout=60.0,
    )
    expected = width * height * 3
    if proc.returncode != 0 or len(proc.stdout) < expected:
        return None
    return np.frombuffer(proc.stdout[:expected], np.uint8).reshape(height, width, 3).copy()
